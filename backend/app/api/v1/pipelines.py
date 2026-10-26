"""Router de pipelines: orquestación radar-01..05 + ETL con bloqueo por orden.

El bloqueo por orden lee ``prod.runs``: una etapa radar solo puede
iniciar si la anterior terminó con estado 'ok' (regla de negocio v1).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.radar import Run
from app.schemas.radar import RunCreate, RunOut, RunUpdate, WorkflowOut

router = APIRouter(prefix="/pipelines", tags=["pipelines"])

#: Etapas válidas: radar-01..05 (n8n) y etl-* (ETL GEIS).
STAGES_RADAR = [f"radar-0{i}" for i in range(1, 6)]
STAGES_ETL = ["etl-denue", "etl-censo"]
STAGES_VALIDOS = STAGES_RADAR + STAGES_ETL

#: Bloqueo por orden: etapa → etapa predecesora que debe estar en 'ok'.
#: Regla R10 del inventario Radar: 02 requiere 01; 03 requiere 02;
#: 04 requiere 02 (NO 03); 01 y 05 no requieren nada.
BLOQUEO_ORDEN: dict[str, str] = {
    "radar-02": "radar-01",
    "radar-03": "radar-02",
    "radar-04": "radar-02",
}


def _ultimo_run(db: Session, pipeline: str) -> Run | None:
    """Último run de un pipeline, o None si nunca corrió."""
    return (
        db.query(Run)
        .filter(Run.pipeline == pipeline)
        .order_by(desc(Run.started_at), desc(Run.run_id))
        .first()
    )


def _ultimo_estado(db: Session, pipeline: str) -> str | None:
    """Estado del último run de un pipeline, o None si nunca corrió."""
    run = _ultimo_run(db, pipeline)
    return run.estado if run else None


def _motivo_bloqueo(stage: str, predecesor: str, ultimo: Run | None) -> str:
    """Motivo diferenciado del 409 (regla R10): nunca / running / error."""
    base = f"{stage} requiere que {predecesor} haya terminado con estado 'ok'"
    if ultimo is None:
        return f"{base}: {predecesor} nunca se ha ejecutado, ejecútala primero"
    if ultimo.estado == "running":
        desde = f" desde {ultimo.started_at}" if ultimo.started_at else ""
        return (
            f"{base}: {predecesor} sigue en ejecución{desde}; "
            "si se atoró, revísala en n8n → Executions"
        )
    if ultimo.estado == "error":
        detalle = (ultimo.detalle or {}).get("error") or "sin detalle"
        return f"{base}: {predecesor} terminó en error. Último detalle: {detalle}"
    return base


def _disparar_n8n(
    stage: str,
    target: dict | None = None,
    giros: list[str] | None = None,
) -> tuple[bool, str]:
    """Dispara el webhook real del workflow en n8n.

    Los workflows 01–05 ya tienen un nodo Webhook con path ``radar-0N`` y
    ellos mismos registran la corrida en ``prod.runs`` (nodo «Registrar
    run»). El backend solo dispara y luego lee la corrida registrada; así
    no se duplican filas ni quedan corridas «running» huérfanas.

    Devuelve ``(ok, detalle)``. Un 404 suele significar que el workflow no
    está activo/publicado en n8n.
    """
    base = os.getenv("N8N_URL", "http://n8n:5678").rstrip("/")
    cuerpo = json.dumps({
        "origen": "geis-api",
        "target": target or {},
        "giros": giros or [],
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/webhook/{stage}",
        data=cuerpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        return True, "n8n aceptó el disparo"
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False, (
                f"n8n no tiene el webhook {stage!r} activo (404). "
                "Activa/publica el workflow en n8n y vuelve a intentar."
            )
        return False, f"n8n respondió {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 — red/timeout
        return False, f"No se pudo contactar n8n: {exc}"


def _esperar_run(db: Session, stage: str, desde: datetime) -> Run | None:
    """Espera (máx. ~6 s) la corrida que registra el workflow en n8n."""
    for _ in range(24):
        db.expire_all()
        run = _ultimo_run(db, stage)
        if run is not None and run.started_at and run.started_at >= desde:
            return run
        time.sleep(0.25)
    return None


def _run_to_out(run: Run) -> RunOut:
    return RunOut(
        run_id=run.run_id,
        pipeline=run.pipeline,
        estado=run.estado,
        detalle=run.detalle,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.post("/run/{stage}", response_model=RunOut, status_code=201)
def correr_stage(
    stage: str,
    payload: RunCreate | None = None,
    db: Session = Depends(get_db),
):
    """Inicia una corrida: crea el run en estado 'running' y devuelve su id.

    Aplica el bloqueo por orden en etapas radar (409 con el motivo si se
    viola). Etapas etl-* no tienen bloqueo.
    """
    if stage not in STAGES_VALIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"stage inválido: {stage!r}; válidos: {', '.join(STAGES_VALIDOS)}",
        )
    predecesor = BLOQUEO_ORDEN.get(stage)
    if predecesor is not None:
        ultimo_run = _ultimo_run(db, predecesor)
        ultimo = ultimo_run.estado if ultimo_run else None
        if ultimo != "ok":
            raise HTTPException(
                status_code=409,
                detail={
                    "motivo": _motivo_bloqueo(stage, predecesor, ultimo_run),
                    "predecesor": predecesor,
                    "ultimo_estado": ultimo,
                },
            )

    # Modo real: se dispara el webhook del workflow. n8n registra la
    # corrida (nodo «Registrar run») y al terminar la marca ok/error.
    if payload and payload.disparar and stage.startswith("radar-"):
        desde = datetime.now(timezone.utc)
        ok, motivo = _disparar_n8n(stage, payload.target, payload.giros)
        if not ok:
            # Deja constancia del fallo en la bitácora para que se vea en
            # Sistema/Operación, pero responde 502 con el motivo claro.
            run = Run(
                pipeline=stage, estado="error",
                detalle={"origen": "geis-api", "error": motivo},
                finished_at=datetime.now(timezone.utc),
            )
            db.add(run)
            db.commit()
            raise HTTPException(status_code=502, detail=motivo)
        run = _esperar_run(db, stage, desde)
        if run is not None:
            return _run_to_out(run)
        raise HTTPException(
            status_code=502,
            detail=(
                f"n8n aceptó el disparo de {stage}, pero el workflow no "
                "registró la corrida en 6 s. Revisa n8n → Executions."
            ),
        )

    run = Run(
        pipeline=stage,
        estado="running",
        detalle=(payload.detalle if payload else None),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _run_to_out(run)


@router.patch("/runs/{run_id}", response_model=RunOut)
def actualizar_run(run_id: int, payload: RunUpdate, db: Session = Depends(get_db)):
    """Actualiza el estado de un run (ok/error) y sella finished_at."""
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} no encontrado")
    run.estado = payload.estado
    if payload.detalle is not None:
        run.detalle = payload.detalle
    if payload.estado in ("ok", "error"):
        run.finished_at = run.finished_at or datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return _run_to_out(run)


@router.get("/runs", response_model=list[RunOut])
def listar_runs(
    pipeline: str | None = Query(default=None, description="Filtra por pipeline"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Bitácora unificada de corridas (n8n + ETL), más recientes primero."""
    q = db.query(Run)
    if pipeline:
        q = q.filter(Run.pipeline == pipeline)
    runs = q.order_by(desc(Run.started_at), desc(Run.run_id)).limit(limit).all()
    return [_run_to_out(r) for r in runs]


def _raiz_proyecto() -> Path:
    """Raíz del proyecto (donde vive ``n8n/workflows``).

    En host el archivo está en ``<raíz>/backend/app/api/v1/pipelines.py``
    (``parents[4]``); dentro del contenedor el backend se monta en ``/code``
    (``parents[3]`` = ``/code``) y los workflows en ``/n8n`` (volume del
    compose). Se prueban candidatos y variables de entorno para que
    ``GET /pipelines/workflows`` funcione en ambos entornos.
    """
    import os

    candidatos: list[Path] = []
    env_raiz = os.getenv("PROJECT_ROOT")
    if env_raiz:
        candidatos.append(Path(env_raiz))
    candidatos.append(Path("/n8n"))
    candidatos.append(Path("/code/n8n"))
    resueltos = Path(__file__).resolve()
    for padre in resueltos.parents:
        candidatos.append(padre)
        candidatos.append(padre / "n8n")
    for candidato in candidatos:
        carpeta = candidato / "workflows" if candidato.name == "n8n" else candidato / "n8n" / "workflows"
        if carpeta.is_dir():
            return candidato.parent if candidato.name == "n8n" else candidato
    # Fallback histórico (host): parents[4] es la raíz del repo.
    return Path(__file__).resolve().parents[4]


@router.get("/workflows", response_model=list[WorkflowOut])
def listar_workflows():
    """Lee los JSON de n8n/workflows/ y devuelve [{id, nombre, descripcion}].

    Si la carpeta no existe aún (fase C pendiente), devuelve lista vacía.
    """
    carpeta = _raiz_proyecto() / "n8n" / "workflows"
    if not carpeta.is_dir():
        return []
    salidas: list[WorkflowOut] = []
    for ruta in sorted(carpeta.glob("*.json")):
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        salidas.append(
            WorkflowOut(
                id=ruta.stem,
                nombre=str(datos.get("nombre") or datos.get("name") or ruta.stem),
                descripcion=datos.get("descripcion") or datos.get("description"),
            )
        )
    return salidas


# Re-export para uso en tests.
def ultimo_estado_pipeline(db: Session, pipeline: str) -> str | None:
    """Estado del último run de un pipeline (helper testeable)."""
    return _ultimo_estado(db, pipeline)
