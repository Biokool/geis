"""Router de pipelines: orquestación radar-01..05 + ETL con bloqueo por orden.

El bloqueo por orden lee ``prod.runs``: una etapa radar solo puede
iniciar si la anterior terminó con estado 'ok' (regla de negocio v1).
"""
from __future__ import annotations

import json
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
BLOQUEO_ORDEN: dict[str, str] = {
    "radar-02": "radar-01",
    "radar-03": "radar-02",
    "radar-04": "radar-03",
}


def _ultimo_estado(db: Session, pipeline: str) -> str | None:
    """Estado del último run de un pipeline, o None si nunca corrió."""
    row = (
        db.query(Run.estado)
        .filter(Run.pipeline == pipeline)
        .order_by(desc(Run.started_at), desc(Run.run_id))
        .first()
    )
    return row[0] if row else None


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
        ultimo = _ultimo_estado(db, predecesor)
        if ultimo != "ok":
            raise HTTPException(
                status_code=409,
                detail={
                    "motivo": (
                        f"{stage} requiere que {predecesor} haya terminado "
                        f"con estado 'ok'"
                    ),
                    "predecesor": predecesor,
                    "ultimo_estado": ultimo,
                },
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
    """Raíz del proyecto (donde vive n8n/, scraper/, signals/)."""
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
