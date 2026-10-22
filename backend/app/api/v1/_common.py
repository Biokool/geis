"""Utilidades compartidas de los routers v1 (linaje, ediciones)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.common import Lineage, make_lineage


def edition_labels(db: Session) -> list[str]:
    """Etiquetas de ediciones de datos presentes (para el linaje)."""
    try:
        rows = db.execute(text(
            "SELECT s.code || ':' || e.edition FROM prod.data_editions e "
            "JOIN prod.data_sources s ON s.source_id = e.source_id "
            "ORDER BY e.ingested_at DESC"
        )).all()
        return [r[0] for r in rows]
    except Exception:
        return []


def lineage(db: Session) -> Lineage:
    """Linaje estándar de una respuesta (ediciones + momento + versión)."""
    return make_lineage(edition_labels(db))
