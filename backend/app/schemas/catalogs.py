"""Esquemas de catálogos y estado del ETL."""
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import Lineage


class ScianOut(BaseModel):
    scian_code: str
    description: str
    sector_code: str
    thermal_intensity: float
    base_attractiveness: float
    lambda_default: float


class ScianListResponse(BaseModel):
    items: list[ScianOut]
    total: int
    lineage: Lineage


class EditionStatus(BaseModel):
    edition_id: int
    source_code: str
    source_name: str
    edition: str
    published_at: date | None
    ingested_at: datetime
    records_total: int | None
    records_valid: int | None
    records_quarantine: int | None
    notes: str | None


class EtlStatusResponse(BaseModel):
    editions: list[EditionStatus]
    lineage: Lineage
