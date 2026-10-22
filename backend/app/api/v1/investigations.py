"""Router de investigaciones: historial CRUD (§7.1 del SRS)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.v1._common import lineage
from app.db.session import get_db
from app.models.investigations import UserInvestigation
from app.schemas.investigations import InvestigationCreate, InvestigationOut

router = APIRouter(prefix="/investigations", tags=["investigations"])

TIPOS_VALIDOS = {
    "location_viability", "b2b_prospecting", "lookalike", "multi_compare", "real_estate",
}
TERRITORIOS_VALIDOS = {
    "point_buffers", "isochrone", "polygon", "ageb", "municipality", "state",
}


@router.post("", response_model=InvestigationOut, status_code=201)
def crear_investigacion(body: InvestigationCreate, db: Session = Depends(get_db)):
    """Crea una investigación en el historial."""
    if body.investigation_type not in TIPOS_VALIDOS:
        raise HTTPException(status_code=422, detail=f"investigation_type inválido: {body.investigation_type}")
    if body.territory_kind not in TERRITORIOS_VALIDOS:
        raise HTTPException(status_code=422, detail=f"territory_kind inválido: {body.territory_kind}")

    inv = UserInvestigation(
        user_id=body.user_id, title=body.title,
        investigation_type=body.investigation_type, vertical=body.vertical,
        territory_kind=body.territory_kind,
        center_lat=body.center_lat, center_lon=body.center_lon,
        radii_m=body.radios_m, params=body.params, status="completed",
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return _to_out(inv, db)


@router.get("", response_model=list[InvestigationOut])
def listar_investigaciones(
    user_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Lista investigaciones del historial (más recientes primero)."""
    q = db.query(UserInvestigation).order_by(UserInvestigation.created_at.desc())
    if user_id:
        q = q.filter(UserInvestigation.user_id == user_id)
    return [_to_out(inv, db) for inv in q.offset(offset).limit(limit).all()]


@router.get("/{investigation_id}", response_model=InvestigationOut)
def leer_investigacion(investigation_id: UUID, db: Session = Depends(get_db)):
    """Lee una investigación por su id."""
    inv = db.get(UserInvestigation, investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigación no encontrada")
    return _to_out(inv, db)


@router.delete("/{investigation_id}", status_code=204)
def eliminar_investigacion(investigation_id: UUID, db: Session = Depends(get_db)):
    """Elimina físicamente una investigación (204 sin cuerpo).

    El modelo no tiene ``deleted_at``, así que el borrado es físico; las
    filas hijas de ``investigation_leads`` se eliminan en la BD por la FK
    con ON DELETE CASCADE.
    """
    inv = db.get(UserInvestigation, investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigación no encontrada")
    db.delete(inv)
    db.commit()
    return Response(status_code=204)


def _to_out(inv: UserInvestigation, db: Session) -> InvestigationOut:
    return InvestigationOut(
        investigation_id=inv.investigation_id, user_id=inv.user_id, title=inv.title,
        investigation_type=inv.investigation_type, vertical=inv.vertical,
        territory_kind=inv.territory_kind, center_lat=float(inv.center_lat) if inv.center_lat else None,
        center_lon=float(inv.center_lon) if inv.center_lon else None,
        radii_m=inv.radii_m, params=inv.params or {}, scores=inv.scores,
        verdict=inv.verdict, status=inv.status, created_at=inv.created_at,
        lineage=lineage(db),
    )
