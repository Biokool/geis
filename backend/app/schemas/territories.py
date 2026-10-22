"""Esquemas del router de territorios."""
from pydantic import BaseModel, Field

from app.schemas.common import Lineage


class GeocodeRequest(BaseModel):
    """Geocodificación: acepta coordenadas directas o una dirección."""

    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = Field(default=None, description="Dirección o link de Maps en texto libre")


class GeocodeResponse(BaseModel):
    lat: float
    lon: float
    label: str
    stub: bool = False
    nota: str | None = None
    lineage: Lineage
