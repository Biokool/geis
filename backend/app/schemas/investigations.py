"""Esquemas de investigaciones (historial CRUD)."""
from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field

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
    # El frontend histórico envía `radii_m` (como el ReportOut) y el Radar
    # envía `radios_m`: se aceptan ambos para no perder los radios en
    # silencio (antes `radii_m` se ignoraba y el mapa no pintaba círculos).
    radios_m: list[int] | None = Field(
        default=None,
        validation_alias=AliasChoices("radios_m", "radii_m"),
        serialization_alias="radii_m",
    )
    params: dict = Field(default_factory=dict)


class InvestigationPatch(BaseModel):
    """Actualización parcial de una investigación.

    ``es_principal``: ganadora persistente del comparador. Al ponerla en
    true, el backend desmarca las demás investigaciones del mismo usuario.
    """

    es_principal: bool | None = None
    title: str | None = None


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
    es_principal: bool = False
    created_at: datetime
    lineage: Lineage
