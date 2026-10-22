"""Modelos del módulo de configuración inicial + IA interna.

Nótese: estas tablas viven en el esquema por defecto (public) y usan
``JSON`` (no ``JSONB``) para que la suite de tests pueda ejercitarlas en
SQLite; en PostgreSQL el comportamiento es equivalente.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CompanyProfile(Base):
    """Versiones del documento PERFIL-EMPRESA.md (solo una activa)."""

    __tablename__ = "company_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vertical_id: Mapped[str | None] = mapped_column(Text)
    nombre: Mapped[str | None] = mapped_column(Text)
    profile_md: Mapped[str | None] = mapped_column(Text)
    profile_json: Mapped[dict | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KnowledgeFact(Base):
    """Hechos aprendidos por vertical: caché de conocimiento del operador.

    ``fact_key`` es único por ``vertical_id`` (upsert). ``source`` indica
    el origen: 'manual', 'system' o 'ai:{provider}'.
    """

    __tablename__ = "knowledge_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vertical_id: Mapped[str] = mapped_column(Text, nullable=False)
    fact_key: Mapped[str] = mapped_column(Text, nullable=False)
    fact_value: Mapped[dict | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )


class AiUsageLog(Base):
    """Bitácora de cada uso de un proveedor de IA (auditoría de costos)."""

    __tablename__ = "ai_usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(Text)
    ok: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
