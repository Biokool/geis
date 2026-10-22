"""Esquemas comunes: linaje de datos presente en todas las respuestas (§7.5)."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.core.config import settings


class Lineage(BaseModel):
    """Linaje: ediciones de datos usadas, momento del cálculo y versión de modelos."""

    editions: list[str] = Field(default_factory=list, description="Ediciones de datos (p. ej. DENUE_11_2023)")
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_version: str = Field(default=settings.model_version)


def make_lineage(editions: list[str] | None = None) -> Lineage:
    """Construye el linaje estándar de una respuesta."""
    return Lineage(editions=editions or [])
