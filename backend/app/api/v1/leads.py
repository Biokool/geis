"""Router de leads: tabla CRM con paginación por cursor.

Incluye el listado DENUE original (GET "") más las leads curadas del
módulo Radar (GET /curados, GET /curados/{id}, PATCH /curados/{id})
sobre ``prod.leads``, y la exportación a CSV (POST /export).
"""
import base64
import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics import b2b_score, completitud_contacto, e_estrato, idt
from app.api.v1._common import lineage
from app.api.v1.analysis import CLIMA_DEFAULT, _intensidad_scian
from app.db.session import get_db
from app.schemas.leads import LeadOut, LeadsPage
from app.schemas.radar import Etapa, LeadCountOut, LeadUpdate, LeadsCuradosPage
from app.schemas.radar import LeadOut as LeadCuradoOut

router = APIRouter(prefix="/leads", tags=["leads"])


def _encode_cursor(denue_id: str) -> str:
    return base64.urlsafe_b64encode(json.dumps({"last": denue_id}).encode()).decode()


def _decode_cursor(cursor: str | None) -> str | None:
    if not cursor:
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode()).get("last")
    except Exception:
        return None


@router.get("", response_model=LeadsPage)
def listar_leads(
    cursor: str | None = Query(default=None, description="Cursor opaco de paginación"),
    limit: int = Query(default=20, ge=1, le=100),
    estrato_min: int | None = Query(default=None, ge=1, le=7),
    scian: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Lista leads (establecimientos) con IDT/score calculados, paginación por cursor."""
    last = _decode_cursor(cursor)
    filtros = ["is_active"]
    params: dict = {"limit": limit + 1}
    if estrato_min:
        filtros.append("estrato_ordinal >= :estrato_min")
        params["estrato_min"] = estrato_min
    if scian:
        filtros.append("scian_code = ANY(:scians)")
        params["scians"] = scian
    if last:
        filtros.append("denue_id > :last")
        params["last"] = last

    filas = db.execute(
        text(
            "SELECT denue_id, nombre, scian_code, scian_desc, estrato_texto, "
            "estrato_ordinal, colonia, municipio, telefono, correo, sitio_web, "
            "lat, lon FROM prod.denue_establishments "
            f"WHERE {' AND '.join(filtros)} ORDER BY denue_id LIMIT :limit"
        ),
        params,
    ).all()

    items: list[LeadOut] = []
    for f in filas[:limit]:
        (denue_id, nombre, scian_code, scian_desc, estrato_txt, estrato_ord,
         colonia, municipio, tel, correo, sitio, lat, lon) = f
        r_idt = idt(int(estrato_ord), _intensidad_scian(db, scian_code), CLIMA_DEFAULT, None)
        s = b2b_score({
            "idt": r_idt["idt"] / 100.0,
            "tamano": e_estrato(int(estrato_ord)),
            "accesibilidad": 0.5,  # sin corredor de referencia en este listado
            "densidad": 0.5,
            "contacto": completitud_contacto(bool(tel), bool(correo), bool(sitio)),
        })
        items.append(LeadOut(
            denue_id=denue_id, nombre=nombre, scian_code=scian_code,
            scian_desc=scian_desc, estrato_texto=estrato_txt,
            estrato_ordinal=int(estrato_ord), colonia=colonia, municipio=municipio,
            telefono=tel, correo=correo, sitio_web=sitio,
            lat=float(lat), lon=float(lon),
            idt=r_idt["idt"], score=s["score"],
        ))

    next_cursor = _encode_cursor(filas[limit - 1][0]) if len(filas) > limit else None
    return LeadsPage(items=items, next_cursor=next_cursor, limit=limit, lineage=lineage(db))


# ------------------------------------------------- exportación CSV
_COLUMNAS_CSV = (
    "denue_id", "nombre", "scian_code", "scian_desc", "estrato_texto",
    "municipio", "telefono", "correo", "sitio_web", "lat", "lon", "idt", "score",
)


def filas_a_csv(filas, intensidades: dict[str, float]) -> str:
    """Convierte filas de ``prod.denue_establishments`` a CSV con IDT y score.

    Función pura (testeable sin BD). Cada fila es la tupla
    (denue_id, nombre, scian_code, scian_desc, estrato_texto, estrato_ordinal,
    municipio, telefono, correo, sitio_web, lat, lon). ``intensidades`` mapea
    scian_code → intensidad térmica (0–1); sin entrada se usa 0.5.
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_COLUMNAS_CSV)
    for f in filas:
        (denue_id, nombre, scian_code, scian_desc, estrato_txt, estrato_ord,
         municipio, tel, correo, sitio, lat, lon) = f
        try:
            r_idt = idt(int(estrato_ord), intensidades.get(scian_code, 0.5),
                        CLIMA_DEFAULT, None)
            s = b2b_score({
                "idt": r_idt["idt"] / 100.0,
                "tamano": e_estrato(int(estrato_ord)),
                "accesibilidad": 0.5,  # sin corredor de referencia en este listado
                "densidad": 0.5,
                "contacto": completitud_contacto(bool(tel), bool(correo), bool(sitio)),
            })
            idt_v, score_v = r_idt["idt"], s["score"]
        except (ValueError, TypeError):
            # Fila con datos inválidos: se exporta sin score en lugar de
            # tumbar la exportación completa.
            idt_v, score_v = None, None
        w.writerow([denue_id, nombre, scian_code, scian_desc, estrato_txt,
                    municipio, tel, correo, sitio, lat, lon, idt_v, score_v])
    return buf.getvalue()


@router.post("/export")
def exportar_leads(
    formato: str = Query(default="csv", description="Formato de exportación"),
    db: Session = Depends(get_db),
):
    """Exporta leads (establecimientos) con IDT y score calculados.

    ``formato=csv`` genera el archivo (límite 5,000 filas). Excel aún no
    está disponible: responde 501 honesto en lugar de un 404.
    """
    if formato == "excel":
        raise HTTPException(
            status_code=501,
            detail="Excel no disponible en esta versión; usa formato=csv",
        )
    if formato != "csv":
        raise HTTPException(
            status_code=422, detail="formato debe ser 'csv'"
        )
    intensidades = {
        r[0]: float(r[1])
        for r in db.execute(
            text("SELECT scian_code, thermal_intensity FROM prod.cat_scian")
        ).all()
    }
    filas = db.execute(
        text(
            "SELECT denue_id, nombre, scian_code, scian_desc, estrato_texto, "
            "estrato_ordinal, municipio, telefono, correo, sitio_web, lat, lon "
            "FROM prod.denue_establishments WHERE is_active "
            "ORDER BY denue_id LIMIT 5000"
        )
    ).all()
    contenido = filas_a_csv(filas, intensidades)
    return StreamingResponse(
        iter([contenido]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


# ------------------------------------------------- leads curadas (Radar)
_COLUMNAS_CURADO = (
    "lead_id, source, nombre, giro, direccion, telefono, web, rating, "
    "score, score_components, linea_recomendada, etapa, temp_zona, notas, "
    "enriquecido_apollo, crm_synced_at, created_at, updated_at, "
    "ST_Y(geom) AS lat, ST_X(geom) AS lon"
)


def _fila_a_curado(f) -> LeadCuradoOut:
    """Mapea una fila SQL de prod.leads al esquema de salida."""
    return LeadCuradoOut(
        lead_id=f[0], source=f[1], nombre=f[2], giro=f[3], direccion=f[4],
        telefono=f[5], web=f[6],
        rating=float(f[7]) if f[7] is not None else None,
        score=float(f[8]) if f[8] is not None else None,
        score_components=f[9] or {},
        linea_recomendada=f[10], etapa=f[11],
        temp_zona=float(f[12]) if f[12] is not None else None,
        notas=f[13], enriquecido_apollo=bool(f[14]), crm_synced_at=f[15],
        lat=float(f[18]) if f[18] is not None else None,
        lon=float(f[19]) if f[19] is not None else None,
        created_at=f[16], updated_at=f[17],
    )


def _encode_curado_cursor(lead_id: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"last": lead_id}).encode()).decode()


def _decode_curado_cursor(cursor: str | None) -> int | None:
    if not cursor:
        return None
    try:
        valor = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode()).get("last")
        return int(valor) if valor is not None else None
    except Exception:
        return None


@router.get("/count", response_model=LeadCountOut)
def contar_leads_curados(
    etapa: Etapa | None = Query(default=None, description="Filtra por etapa comercial"),
    linea: str | None = Query(default=None, description="Filtra por linea_recomendada"),
    source: str | None = Query(default=None, description="Filtra por origen"),
    db: Session = Depends(get_db),
):
    """Conteo total de leads curadas (prod.leads), sin paginación.

    Es el total del badge del menú y del KPI de Inicio. Acepta los mismos
    filtros que ``GET /leads/curados`` (etapa, linea, source), con WHERE
    dinámico parametrizado.
    """
    filtros: list[str] = []
    params: dict = {}
    if etapa:
        filtros.append("etapa = :etapa")
        params["etapa"] = etapa
    if linea:
        filtros.append("linea_recomendada = :linea")
        params["linea"] = linea
    if source:
        filtros.append("source = :source")
        params["source"] = source

    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    total = db.execute(
        text(f"SELECT COUNT(*) FROM prod.leads {where}"),
        params,
    ).scalar()
    return LeadCountOut(total=int(total or 0))


@router.get("/curados", response_model=LeadsCuradosPage)
def listar_leads_curados(
    etapa: Etapa | None = Query(default=None, description="Filtra por etapa comercial"),
    linea: str | None = Query(default=None, description="Filtra por linea_recomendada"),
    source: str | None = Query(default=None, description="Filtra por origen"),
    cursor: str | None = Query(default=None, description="Cursor opaco de paginación"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Leads curadas (prod.leads) con paginación por cursor."""
    last = _decode_curado_cursor(cursor)
    filtros: list[str] = []
    params: dict = {"limit": limit + 1}
    if etapa:
        filtros.append("etapa = :etapa")
        params["etapa"] = etapa
    if linea:
        filtros.append("linea_recomendada = :linea")
        params["linea"] = linea
    if source:
        filtros.append("source = :source")
        params["source"] = source
    if last is not None:
        filtros.append("lead_id > :last")
        params["last"] = last

    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    filas = db.execute(
        text(f"SELECT {_COLUMNAS_CURADO} FROM prod.leads {where} "
             "ORDER BY lead_id LIMIT :limit"),
        params,
    ).all()

    items = [_fila_a_curado(f) for f in filas[:limit]]
    next_cursor = _encode_curado_cursor(filas[limit - 1][0]) if len(filas) > limit else None
    return LeadsCuradosPage(items=items, next_cursor=next_cursor, limit=limit)


@router.get("/curados/{lead_id}", response_model=LeadCuradoOut)
def obtener_lead_curado(lead_id: int, db: Session = Depends(get_db)):
    """Detalle de una lead curada."""
    fila = db.execute(
        text(f"SELECT {_COLUMNAS_CURADO} FROM prod.leads WHERE lead_id = :lid"),
        {"lid": lead_id},
    ).first()
    if fila is None:
        raise HTTPException(status_code=404, detail=f"lead {lead_id} no encontrado")
    return _fila_a_curado(fila)


@router.patch("/curados/{lead_id}", response_model=LeadCuradoOut)
def actualizar_lead_curado(lead_id: int, payload: LeadUpdate, db: Session = Depends(get_db)):
    """Actualiza etapa y/o notas de una lead curada."""
    sets: list[str] = []
    params: dict = {"lid": lead_id}
    if payload.etapa is not None:
        sets.append("etapa = :etapa")
        params["etapa"] = payload.etapa
    if payload.notas is not None:
        sets.append("notas = :notas")
        params["notas"] = payload.notas
    if not sets:
        raise HTTPException(status_code=422, detail="nada que actualizar (etapa/notas)")
    sets.append("updated_at = :ahora")
    params["ahora"] = datetime.now().astimezone()

    res = db.execute(
        text(f"UPDATE prod.leads SET {', '.join(sets)} WHERE lead_id = :lid"),
        params,
    )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"lead {lead_id} no encontrado")
    db.commit()
    fila = db.execute(
        text(f"SELECT {_COLUMNAS_CURADO} FROM prod.leads WHERE lead_id = :lid"),
        {"lid": lead_id},
    ).first()
    # Auto-aprendizaje: una conversión ('ganado') alimenta knowledge_facts
    # con source='system'. try/except para no romper el flujo si falla.
    if payload.etapa == "ganado":
        try:
            from app.ai import knowledge as _knowledge
            from app.company import store as _store

            giro = fila[3] if fila is not None else None
            _knowledge.save_fact(
                db,
                _store.active_vertical_id(db),
                f"conversion:{giro or 'sin_giro'}",
                {
                    "lead_id": lead_id,
                    "nombre": fila[2] if fila is not None else None,
                    "giro": giro,
                    "score": float(fila[8])
                    if fila is not None and fila[8] is not None
                    else None,
                },
                source="system",
                confidence=1.0,
            )
        except Exception:
            pass
    return _fila_a_curado(fila)
