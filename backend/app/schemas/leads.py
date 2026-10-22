"""Esquemas de leads (tabla CRM)."""
from pydantic import BaseModel

from app.schemas.common import Lineage


class LeadOut(BaseModel):
    denue_id: str
    nombre: str
    scian_code: str
    scian_desc: str | None = None
    estrato_texto: str
    estrato_ordinal: int
    colonia: str | None = None
    municipio: str | None = None
    telefono: str | None = None
    correo: str | None = None
    sitio_web: str | None = None
    lat: float
    lon: float
    idt: float | None = None
    score: float | None = None


class LeadsPage(BaseModel):
    items: list[LeadOut]
    next_cursor: str | None = None
    limit: int
    lineage: Lineage
