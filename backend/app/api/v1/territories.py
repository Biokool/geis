"""Router de territorios: geocodificación y utilidades territoriales."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1._common import lineage
from app.db.session import get_db
from app.schemas.territories import GeocodeRequest, GeocodeResponse

router = APIRouter(prefix="/territories", tags=["territories"])

#: Punto por defecto (CDMX, Zócalo) cuando solo se da una dirección en modo stub.
CDMX_DEFAULT = (19.4326, -99.1332)


@router.post("/geocode", response_model=GeocodeResponse)
def geocode(body: GeocodeRequest, db: Session = Depends(get_db)) -> GeocodeResponse:
    """Convierte {lat, lon} o {address} en un punto confirmado.

    Con coordenadas hace eco y las valida; con dirección en texto libre
    geocodifica a CDMX por defecto y marca ``stub: true`` (fase 2: conector
    de geocoding real).
    """
    if body.lat is not None and body.lon is not None:
        return GeocodeResponse(
            lat=body.lat, lon=body.lon,
            label=f"Punto {body.lat:.5f}, {body.lon:.5f}",
            stub=False, lineage=lineage(db),
        )
    if body.address:
        lat, lon = CDMX_DEFAULT
        return GeocodeResponse(
            lat=lat, lon=lon,
            label=f"Geocodificado (stub): {body.address}",
            stub=True,
            nota="Sin conector de geocoding: se devuelve CDMX por defecto. Fase 2: geocoding real.",
            lineage=lineage(db),
        )
    from fastapi import HTTPException
    raise HTTPException(status_code=422, detail="Se requiere {lat, lon} o {address}")
