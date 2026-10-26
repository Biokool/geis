"""Esquemas de reportes de ubicación (§6.5 del SRS)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import Lineage


class ReportCreate(BaseModel):
    investigation_id: UUID | None = None
    title: str = "Reporte de ubicación"
    giro: str | None = None
    scian: str | None = None
    lat: float | None = None
    lon: float | None = None
    radios: list[int] = [1000, 2000]
    # Overrides opcionales de supuestos TAM (ganan sobre la ficha sectorial
    # y sobre el default). gasto en MXN/mes por persona objetivo.
    gasto_promedio_mensual: float | None = Field(default=None, gt=0)
    f_nse: float | None = Field(default=None, gt=0)
    f_pen: float | None = Field(default=None, gt=0, le=1)


class ReportOut(BaseModel):
    report_id: UUID
    title: str
    verdict: str | None
    payload: dict
    created_at: datetime
    lineage: Lineage


# ------------------------------------------------------------- compartir --
class ShareCreate(BaseModel):
    """Crear un link invitado para un reporte (token opaco expirable)."""

    dias: int = Field(default=30, ge=1, le=365, description="Vigencia del link en días")


class ShareOut(BaseModel):
    token: str
    url: str = Field(description="Ruta pública del reporte: /r/{token}")
    expira_en: datetime


class SharedReportOut(BaseModel):
    """Vista pública de solo lectura de un reporte compartido."""

    report_id: UUID
    title: str
    verdict: str | None
    payload: dict
    expira_en: datetime | None = None
