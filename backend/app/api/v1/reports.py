"""Router de reportes de ubicación (§6.5 del SRS): genera y lee el JSON de 14 secciones.

La generación usa ``build_report_context`` para poblar TODAS las claves
del builder (demanda AGEB, hogares, NSE, entorno por 9 categorías,
competencia con lista, atractores, isócronas, vialidades/movilidad y
fuentes nominales); antes solo llegaban anillos/TAM/Huff.

Compartir (Sección 1): tokens opacos expirables/revocables en
``prod.report_shares``; la vista pública es ``GET /reports/shared/{token}``
(el frontend la sirve en la ruta ``/r/{token}``).
"""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.v1._common import edition_labels, lineage
from app.api.v1.analysis import compute_location_analysis
from app.core.config import settings
from app.db.session import get_db, safe_rollback
from app.geo.geocoding import componentes_de, etiqueta_legible, nominatim_reverse
from app.models.investigations import UserInvestigation
from app.models.reports import Report, ReportShare
from app.reports.builder import build_location_report
from app.reports.context import build_report_context
from app.schemas.reports import (
    ReportCreate,
    ReportOut,
    ShareCreate,
    SharedReportOut,
    ShareOut,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _etiqueta_y_componentes(lat: float, lon: float) -> tuple[str, bool]:
    """Etiqueta legible vía reverse (OSM); (etiqueta, vino_de_reverse)."""
    try:
        datos = nominatim_reverse(lat, lon)
    except Exception:
        datos = None
    if datos:
        comp = componentes_de(datos.get("address"))
        if any(comp.get(k) for k in ("colonia", "municipio", "entidad")):
            return etiqueta_legible(comp, lat, lon), True
    return f"{lat:.5f}, {lon:.5f}", False


@router.post("", response_model=ReportOut, status_code=201)
def generar_reporte(body: ReportCreate, db: Session = Depends(get_db)):
    """Genera un reporte de ubicación completo, lo persiste y devuelve su id."""
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

    overrides = {
        k: v for k, v in {
            "gasto_promedio_mensual": body.gasto_promedio_mensual,
            "f_nse": body.f_nse, "f_pen": body.f_pen,
        }.items() if v is not None
    }
    if overrides:
        analisis = compute_location_analysis(
            db, giro, scian, lat, lon, radios, tam_overrides=overrides,
        )
    else:
        analisis = compute_location_analysis(db, giro, scian, lat, lon, radios)

    etiqueta, con_geocoding = _etiqueta_y_componentes(lat, lon)
    ctx = build_report_context(
        db,
        giro=analisis["giro"], scian=analisis["scian"],
        lat=lat, lon=lon, radios=radios, analisis=analisis,
        etiqueta_ubicacion=etiqueta, con_geocoding=con_geocoding,
    )
    ctx.update({
        "titulo": body.title,
        "supuestos": [
            f"gasto_pc={analisis['tam_supuestos']['gasto_pc_mxn_anual']} "
            f"({analisis['tam_supuestos']['fuente']})",
            f"f_nse={analisis['tam_supuestos']['f_nse']}, f_pen={analisis['tam_supuestos']['f_pen']}",
        ],
        "ediciones": edition_labels(db),
        "model_version": settings.model_version,
    })
    payload = build_location_report(ctx)

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
        safe_rollback(db)

    return _to_out(reporte, db)


@router.get("/{report_id}", response_model=ReportOut)
def leer_reporte(report_id: UUID, db: Session = Depends(get_db)):
    """Lee el JSON persistido de un reporte."""
    reporte = db.get(Report, report_id)
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return _to_out(reporte, db)


# ------------------------------------------------------------- compartir --
def _buscar_share(db: Session, token: str) -> ReportShare | None:
    """Share por token (query estándar; mockeable con sesiones fake)."""
    try:
        return (
            db.query(ReportShare)
            .filter(ReportShare.token == token)
            .first()
        )
    except Exception:
        return None


def _share_vigente(share: ReportShare | None) -> bool:
    if share is None or share.revoked_at is not None:
        return False
    if share.expires_at is not None:
        expira = share.expires_at
        if expira.tzinfo is None:
            expira = expira.replace(tzinfo=timezone.utc)
        if expira <= datetime.now(timezone.utc):
            return False
    return True


@router.post("/{report_id}/share", response_model=ShareOut, status_code=201)
def crear_share(report_id: UUID, body: ShareCreate, db: Session = Depends(get_db)):
    """Crea un link invitado para el reporte (token opaco, expirable)."""
    reporte = db.get(Report, report_id)
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    token = secrets.token_urlsafe(32)
    expira = datetime.now(timezone.utc) + timedelta(days=body.dias)
    share = ReportShare(report_id=report_id, token=token, expires_at=expira)
    db.add(share)
    db.commit()
    return ShareOut(token=token, url=f"/r/{token}", expira_en=expira)


@router.get("/shared/{token}", response_model=SharedReportOut)
def leer_reporte_compartido(token: str, db: Session = Depends(get_db)):
    """Vista pública de solo lectura de un reporte compartido."""
    share = _buscar_share(db, token)
    if not _share_vigente(share):
        raise HTTPException(status_code=404, detail="Link compartido no válido o expirado")
    reporte = db.get(Report, share.report_id)
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    # El link invitado es para el prospecto: se excluye el plan de contacto
    # interno (playbook comercial del owner) del payload público.
    payload = dict(reporte.payload or {})
    payload.pop("plan_contacto", None)
    return SharedReportOut(
        report_id=reporte.report_id, title=reporte.title,
        verdict=reporte.verdict, payload=payload,
        expira_en=share.expires_at,
    )


@router.delete("/{report_id}/share/{token}", status_code=204)
def revocar_share(report_id: UUID, token: str, db: Session = Depends(get_db)):
    """Revoca un link compartido (el GET público pasa a responder 404)."""
    share = _buscar_share(db, token)
    if share is None or share.report_id != report_id:
        raise HTTPException(status_code=404, detail="Link compartido no encontrado")
    share.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)


def _to_out(reporte: Report, db: Session) -> ReportOut:
    return ReportOut(
        report_id=reporte.report_id,
        title=reporte.title, verdict=reporte.verdict,
        payload=reporte.payload, created_at=reporte.created_at,
        lineage=lineage(db),
    )
