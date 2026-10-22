"""Router de reportes de ubicación (§6.5 del SRS): genera y lee el JSON de 13 secciones."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1._common import edition_labels, lineage
from app.api.v1.analysis import compute_location_analysis
from app.core.config import settings
from app.db.session import get_db
from app.models.investigations import UserInvestigation
from app.models.reports import Report
from app.reports.builder import build_location_report
from app.schemas.reports import ReportCreate, ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportOut, status_code=201)
def generar_reporte(body: ReportCreate, db: Session = Depends(get_db)):
    """Genera un reporte de ubicación, lo persiste y devuelve su id."""
    lat, lon, giro, scian, radios = body.lat, body.lon, body.giro, body.scian, body.radios
    investigation_id = body.investigation_id

    if investigation_id:
        inv = db.get(UserInvestigation, investigation_id)
        if not inv:
            raise HTTPException(status_code=404, detail="Investigación no encontrada")
        lat = lat or (float(inv.center_lat) if inv.center_lat else None)
        lon = lon or (float(inv.center_lon) if inv.center_lon else None)
        radios = radios or inv.radii_m or [1000, 2000]
        giro = giro or inv.params.get("giro")
        scian = scian or inv.params.get("scian")

    if lat is None or lon is None:
        raise HTTPException(status_code=422, detail="Se requiere lat/lon o una investigación con centro")

    analisis = compute_location_analysis(db, giro, scian, lat, lon, radios)
    payload = build_location_report({
        "titulo": body.title,
        "giro": analisis["giro"], "scian": analisis["scian"],
        "lat": lat, "lon": lon,
        "etiqueta_ubicacion": f"{lat:.5f}, {lon:.5f}",
        "radios": radios,
        "anillos": analisis["anillos"],
        "tam_mxn": analisis["tam_mxn"], "tam_rango": analisis["tam_rango"],
        "huff": analisis["huff"],
        "supuestos": [
            f"gasto_pc={analisis['tam_supuestos']['gasto_pc_mxn_anual']} "
            f"({analisis['tam_supuestos']['fuente']})",
            f"f_nse={analisis['tam_supuestos']['f_nse']}, f_pen={analisis['tam_supuestos']['f_pen']}",
        ],
        "advertencias": analisis["advertencias"],
        "ediciones": edition_labels(db),
        "model_version": settings.model_version,
    })

    reporte = Report(
        investigation_id=investigation_id, title=body.title,
        verdict=payload["veredicto"]["decision"], payload=payload,
    )
    db.add(reporte)
    db.commit()
    db.refresh(reporte)

    # Auto-aprendizaje: el reporte alimenta knowledge_facts con el
    # veredicto y el ISM promedio. try/except para no romper el flujo.
    try:
        import hashlib as _hashlib

        from app.ai import knowledge as _knowledge
        from app.company import store as _store

        territorio_hash = _hashlib.sha1(
            f"{lat:.4f},{lon:.4f}".encode()
        ).hexdigest()[:8]
        isms = [
            a.get("ism")
            for a in (analisis.get("anillos") or [])
            if a.get("ism") is not None
        ]
        ism_prom = sum(isms) / len(isms) if isms else None
        _knowledge.save_fact(
            db,
            _store.active_vertical_id(db),
            f"report_insight:{territorio_hash}",
            {
                "veredicto": payload["veredicto"]["decision"],
                "ism": ism_prom,
                "lat": lat, "lon": lon,
                "giro": analisis.get("giro"),
            },
            source="system",
            confidence=1.0,
        )
    except Exception:
        pass

    return _to_out(reporte, db)


@router.get("/{report_id}", response_model=ReportOut)
def leer_reporte(report_id: UUID, db: Session = Depends(get_db)):
    """Lee el JSON persistido de un reporte."""
    reporte = db.get(Report, report_id)
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return _to_out(reporte, db)


def _to_out(reporte: Report, db: Session) -> ReportOut:
    return ReportOut(
        report_id=reporte.report_id,
        title=reporte.title, verdict=reporte.verdict,
        payload=reporte.payload, created_at=reporte.created_at,
        lineage=lineage(db),
    )
