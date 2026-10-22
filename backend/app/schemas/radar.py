"""Esquemas del módulo Radar (fusión GEIS × Biokool): leads curadas,
pipelines, providers, señales, propuestas, clima y salud del sistema.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Etapa = Literal["nuevo", "contactado", "reunion", "propuesta", "ganado", "perdido"]
Linea = Literal["koolkat", "solar", "evaporativa"]
Source = Literal["denue", "gmaps", "manual", "linkedin"]
RunEstado = Literal["running", "ok", "error"]
ProviderMode = Literal["local", "cloud", "disabled"]


# ---------------------------------------------------------------- leads
class LeadOut(BaseModel):
    """Lead curado con lat/lon derivados del geom (Point 4326)."""

    lead_id: int
    source: str
    nombre: str
    giro: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    web: str | None = None
    rating: float | None = None
    score: float | None = None
    score_components: dict = Field(default_factory=dict)
    linea_recomendada: str | None = None
    etapa: str
    temp_zona: float | None = None
    notas: str | None = None
    enriquecido_apollo: bool = False
    crm_synced_at: datetime | None = None
    lat: float | None = Field(default=None, description="ST_Y del geom")
    lon: float | None = Field(default=None, description="ST_X del geom")
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LeadUpdate(BaseModel):
    """PATCH de lead: etapa y/o notas (ambos opcionales)."""

    etapa: Etapa | None = None
    notas: str | None = None


class LeadsCuradosPage(BaseModel):
    items: list[LeadOut]
    next_cursor: str | None = None
    limit: int


class LeadCountOut(BaseModel):
    """Conteo total de leads curadas (prod.leads)."""

    total: int


# ---------------------------------------------------------------- pipelines
class RunCreate(BaseModel):
    detalle: dict | None = None


class RunOut(BaseModel):
    run_id: int
    pipeline: str
    estado: str
    detalle: dict | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunUpdate(BaseModel):
    """PATCH de run: nuevo estado y detalle opcional."""

    estado: RunEstado
    detalle: dict | None = None


class WorkflowOut(BaseModel):
    id: str
    nombre: str
    descripcion: str | None = None


# ---------------------------------------------------------------- providers
class ProviderOut(BaseModel):
    name: str
    kind: str
    mode: str
    provider: str
    config: dict = Field(default_factory=dict)
    enabled: bool


class ProviderUpdate(BaseModel):
    mode: ProviderMode | None = None
    provider: str | None = None
    config: dict | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------- señales
class SignalIn(BaseModel):
    titulo: str
    detalle: str | None = None
    empresa_ref: str | None = None
    fuente: str = "manual"


class SignalOut(BaseModel):
    signal_id: int
    fuente: str
    titulo: str | None = None
    detalle: str | None = None
    empresa_ref: str | None = None
    procesada: bool = False
    created_at: datetime | None = None


# ---------------------------------------------------------------- propuestas
class ProposalIn(BaseModel):
    lead_id: int
    titulo: str | None = None
    linea: Linea | None = None
    monto: float | None = None


class ProposalOut(BaseModel):
    proposal_id: int
    lead_id: int
    titulo: str | None = None
    linea: str | None = None
    monto: float | None = None
    estado: str
    created_at: datetime | None = None


class ProposalUpdate(BaseModel):
    titulo: str | None = None
    linea: Linea | None = None
    monto: float | None = None
    estado: str | None = None


# ---------------------------------------------------------------- clima y sistema
class WeatherOut(BaseModel):
    lat: float
    lon: float
    temperature_c: float | None = None
    fetched_at: datetime
    cached: bool = False


class SystemHealth(BaseModel):
    postgres: str
    n8n: str
    scraper: str
    providers: dict[str, dict] = Field(default_factory=dict)


# ---------------------------------------------------------------- linkedin
class LinkedinStatOut(BaseModel):
    stat_id: int
    org_id: str | None = None
    followers: int | None = None
    posts_count: int | None = None
    engagement_total: int | None = None
    stats_date: date | None = None
