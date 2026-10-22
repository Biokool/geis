"""Catálogos y linaje de datos (§5.1 del SRS): fuentes, ediciones, SCIAN, giros y parámetros."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DataSource(Base):
    """Fuente de datos (DENUE, CPV2020, Marco Geoestadístico...)."""

    __tablename__ = "data_sources"
    __table_args__ = {"schema": "prod"}

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    license: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DataEdition(Base):
    """Edición ingerida de una fuente (p. ej. DENUE_11_2023)."""

    __tablename__ = "data_editions"
    __table_args__ = (
        UniqueConstraint("source_id", "edition"),
        {"schema": "prod"},
    )

    edition_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("prod.data_sources.source_id"), nullable=False
    )
    edition: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[date | None] = mapped_column(Date)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    records_total: Mapped[int | None] = mapped_column(BigInteger)
    records_valid: Mapped[int | None] = mapped_column(BigInteger)
    records_quarantine: Mapped[int | None] = mapped_column(BigInteger)
    notes: Mapped[str | None] = mapped_column(Text)


class CatScian(Base):
    """Catálogo SCIAN con intensidad térmica (IDT §3.4) y atractivo base (Huff §3.2)."""

    __tablename__ = "cat_scian"

    scian_code: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    scian_version: Mapped[str] = mapped_column(Text, nullable=False, default="2023")
    sector_code: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    thermal_intensity: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, default=0.50
    )
    base_attractiveness: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, default=0.50
    )
    lambda_default: Mapped[float] = mapped_column(
        Numeric(4, 2), nullable=False, default=2.00
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("thermal_intensity BETWEEN 0 AND 1"),
        CheckConstraint("base_attractiveness BETWEEN 0 AND 1"),
        {"schema": "prod"},
    )


class CatGiroScian(Base):
    """Mapeo texto-libre de giro → clases SCIAN sugeridas."""

    __tablename__ = "cat_giro_scian"
    __table_args__ = (
        UniqueConstraint("giro_label", "scian_code"),
        {"schema": "prod"},
    )

    giro_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    giro_label: Mapped[str] = mapped_column(Text, nullable=False)
    scian_code: Mapped[str] = mapped_column(
        ForeignKey("prod.cat_scian.scian_code"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=1.00)


class ModelParam(Base):
    """Parámetros de modelos por vertical (pesos IDT, score, benchmarks ISM)."""

    __tablename__ = "model_params"
    __table_args__ = (
        UniqueConstraint("vertical", "model", "version"),
        {"schema": "prod"},
    )

    param_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vertical: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
