"""Esquemas de investigaciones (historial CRUD)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import Lineage


class InvestigationCreate(BaseModel):
    title: str
    investigation_type: str = Field(
        description="location_viability | b2b_prospecting | lookalike | multi_compare | real_estate"
    )
    user_id: str = Field(default="guest")
    vertical: str | None = None
    territory_kind: str = Field(default="point_buffers")
    center_lat: float | None = None
    center_lon: float | None = None
    radios_m: list[int] | None = None
    params: dict = Field(default_factory=dict)


class InvestigationOut(BaseModel):
    investigation_id: UUID
    user_id: str
    title: str
    investigation_type: str
    vertical: str | None
    territory_kind: str
    center_lat: float | None
    center_lon: float | None
    radii_m: list[int] | None
    params: dict
    scores: dict | None
    verdict: str | None
    status: str
    created_at: datetime
    lineage: Lineage
