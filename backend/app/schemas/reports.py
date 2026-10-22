"""Esquemas de reportes de ubicación (§6.5 del SRS)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import Lineage


class ReportCreate(BaseModel):
    investigation_id: UUID | None = None
    title: str = "Reporte de ubicación"
    giro: str | None = None
    scian: str | None = None
    lat: float | None = None
    lon: float | None = None
    radios: list[int] = [1000, 2000]


class ReportOut(BaseModel):
    report_id: UUID
    title: str
    verdict: str | None
    payload: dict
    created_at: datetime
    lineage: Lineage
