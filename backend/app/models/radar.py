"""Modelos de la fusión GEIS × Biokool Radar (módulo de ejecución).

Espejo del DDL de la migración 0002: leads curadas, staging del scraper,
bitácora de pipelines, providers anti-cautiverio, propuestas, señales
cálidas y estadísticas de LinkedIn.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: Etapas del pipeline comercial de un lead (Radar §1.2).
ETAPAS_LEAD = ("nuevo", "contactado", "reunion", "propuesta", "ganado", "perdido")

#: Líneas de producto Biokool recomendables por lead.
LINEAS = ("koolkat", "solar", "evaporativa")

#: Orígenes posibles de un lead.
SOURCES = ("denue", "gmaps", "manual", "linkedin")


class Lead(Base):
    """Lead curado: converge investigation_leads (GEIS) + leads (Radar).

    Un lead puede nacer del DENUE (denue_id), del scrapeo (gmaps) o manual.
    """

    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint(f"source IN {SOURCES}"),
        CheckConstraint(f"etapa IN {ETAPAS_LEAD}"),
        CheckConstraint(f"linea_recomendada IN {LINEAS}"),
        UniqueConstraint("source", "nombre", "direccion",
                         name="uq_leads_source_nombre_direccion"),
        {"schema": "prod"},
    )

    lead_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    denue_id: Mapped[str | None] = mapped_column(Text)
    cve_ent: Mapped[str | None] = mapped_column(Text)
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prod.user_investigations.investigation_id", ondelete="SET NULL"),
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    giro: Mapped[str | None] = mapped_column(Text)
    direccion: Mapped[str | None] = mapped_column(Text, server_default="")
    geom: Mapped[str | None] = mapped_column(Geometry("POINT", 4326))
    telefono: Mapped[str | None] = mapped_column(Text)
    web: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    empleados_est: Mapped[int | None] = mapped_column(SmallInteger)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    score_components: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    linea_recomendada: Mapped[str | None] = mapped_column(Text)
    etapa: Mapped[str] = mapped_column(Text, nullable=False, default="nuevo")
    temp_zona: Mapped[float | None] = mapped_column(Numeric(4, 1))
    notas: Mapped[str | None] = mapped_column(Text, server_default="")
    enriquecido_apollo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    crm_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LeadRaw(Base):
    """Staging crudo del scraper (Google Maps) antes del dedup/score."""

    __tablename__ = "leads_raw"
    __table_args__ = ({"schema": "stg"},)

    raw_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str | None] = mapped_column(Text)
    giro: Mapped[str | None] = mapped_column(Text)
    direccion: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[str | None] = mapped_column(Geometry("POINT", 4326))
    telefono: Mapped[str | None] = mapped_column(Text)
    web: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    fuente: Mapped[str | None] = mapped_column(Text, server_default="google_maps")
    query: Mapped[str | None] = mapped_column(Text)
    procesado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Run(Base):
    """Bitácora de ejecuciones de pipelines (radar-01..05 y etl-*).

    Base del bloqueo por orden: una etapa solo corre si la anterior
    terminó con estado 'ok'.
    """

    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("estado IN ('running','ok','error')"),
        {"schema": "prod"},
    )

    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pipeline: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(Text, nullable=False)
    detalle: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Provider(Base):
    """Capa anti-cautiverio: cada capacidad tiene modo local/cloud/disabled."""

    __tablename__ = "providers"
    __table_args__ = (
        CheckConstraint("mode IN ('local','cloud','disabled')"),
        {"schema": "prod"},
    )

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="local")
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="local")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Proposal(Base):
    """Propuesta comercial asociada a un lead (fase 2 del módulo Radar)."""

    __tablename__ = "proposals"
    __table_args__ = ({"schema": "prod"},)

    proposal_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("prod.leads.lead_id", ondelete="CASCADE"), nullable=False
    )
    titulo: Mapped[str | None] = mapped_column(Text)
    linea: Mapped[str | None] = mapped_column(Text)
    monto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    estado: Mapped[str] = mapped_column(Text, nullable=False, default="borrador")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WarmSignal(Base):
    """Señal cálida: manual (SDR) o de LinkedIn; suma al score al procesarse."""

    __tablename__ = "warm_signals"
    __table_args__ = ({"schema": "prod"},)

    signal_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    fuente: Mapped[str] = mapped_column(Text, nullable=False, default="linkedin")
    titulo: Mapped[str | None] = mapped_column(Text)
    detalle: Mapped[str | None] = mapped_column(Text)
    empresa_ref: Mapped[str | None] = mapped_column(Text)
    procesada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LinkedinStat(Base):
    """Métricas diarias de la página de empresa de LinkedIn."""

    __tablename__ = "linkedin_stats"
    __table_args__ = (
        UniqueConstraint("org_id", "stats_date", name="uq_linkedin_org_date"),
        {"schema": "prod"},
    )

    stat_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str | None] = mapped_column(Text)
    followers: Mapped[int | None] = mapped_column(Integer)
    posts_count: Mapped[int | None] = mapped_column(Integer)
    engagement_total: Mapped[int | None] = mapped_column(Integer)
    stats_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    raw: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
