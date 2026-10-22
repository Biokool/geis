"""Router del ETL: estado de las ingestas (ediciones de datos)."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1._common import lineage
from app.db.session import get_db
from app.schemas.catalogs import EditionStatus, EtlStatusResponse

router = APIRouter(prefix="/etl", tags=["etl"])


@router.get("/status", response_model=EtlStatusResponse)
def estado_etl(db: Session = Depends(get_db)):
    """Estado de las ediciones ingeridas (fuente, edición, conteos)."""
    filas = db.execute(
        text(
            "SELECT e.edition_id, s.code, s.name, e.edition, e.published_at, "
            "e.ingested_at, e.records_total, e.records_valid, "
            "e.records_quarantine, e.notes "
            "FROM prod.data_editions e "
            "JOIN prod.data_sources s ON s.source_id = e.source_id "
            "ORDER BY e.ingested_at DESC"
        )
    ).all()
    ediciones = [
        EditionStatus(
            edition_id=f[0], source_code=f[1], source_name=f[2], edition=f[3],
            published_at=f[4], ingested_at=f[5], records_total=f[6],
            records_valid=f[7], records_quarantine=f[8], notes=f[9],
        )
        for f in filas
    ]
    return EtlStatusResponse(editions=ediciones, lineage=lineage(db))
