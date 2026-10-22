"""Router de catálogos: SCIAN con intensidades térmicas."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1._common import lineage
from app.db.session import get_db
from app.schemas.catalogs import ScianListResponse, ScianOut

router = APIRouter(prefix="/catalogs", tags=["catalogs"])


@router.get("/scian", response_model=ScianListResponse)
def listar_scian(db: Session = Depends(get_db)):
    """Catálogo SCIAN con intensidad térmica (IDT) y atractivo base (Huff)."""
    filas = db.execute(
        text(
            "SELECT scian_code, description, sector_code, thermal_intensity, "
            "base_attractiveness, lambda_default FROM prod.cat_scian ORDER BY scian_code"
        )
    ).all()
    items = [
        ScianOut(
            scian_code=f[0], description=f[1], sector_code=f[2],
            thermal_intensity=float(f[3]), base_attractiveness=float(f[4]),
            lambda_default=float(f[5]),
        )
        for f in filas
    ]
    return ScianListResponse(items=items, total=len(items), lineage=lineage(db))
