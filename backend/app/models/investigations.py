"""Investigaciones de usuarios y leads persistidos (§5.5 y §7.1 del SRS)."""
from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserInvestigation(Base):
    """Investigación de un usuario: territorio, parámetros versionados y scores."""

    __tablename__ = "user_investigations"
    __table_args__ = (
        CheckConstraint(
            "investigation_type IN ('location_viability','b2b_prospecting',"
            "'lookalike','multi_compare','real_estate')"
        ),
        CheckConstraint(
            "territory_kind IN ('point_buffers','isochrone','polygon','ageb',"
            "'municipality','state')"
        ),
        CheckConstraint(
            "verdict IN ('AVANZAR','NEGOCIAR','EXPLORAR_OTRA_ZONA')"
        ),
        CheckConstraint("status IN ('running','completed','failed')"),
        {"schema": "prod"},
    )

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    investigation_type: Mapped[str] = mapped_column(Text, nullable=False)
    vertical: Mapped[str | None] = mapped_column(Text)

    territory_geojson: Mapped[str | None] = mapped_column(Geometry("GEOMETRY", 4326))
    territory_kind: Mapped[str] = mapped_column(Text, nullable=False)
    center_lat: Mapped[float | None] = mapped_column(Numeric(9, 6))
    center_lon: Mapped[float | None] = mapped_column(Numeric(9, 6))
    radii_m: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    isochrone_min: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))

    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    params_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scores: Mapped[dict | None] = mapped_column(JSONB)
    verdict: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="completed")

    edition_id: Mapped[int | None] = mapped_column(
        ForeignKey("prod.data_editions.edition_id")
    )
    model_params_version: Mapped[int | None] = mapped_column(Integer)
    report_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    share_token: Mapped[str | None] = mapped_column(Text, unique=True)
    share_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InvestigationLead(Base):
    """Lead generado por una investigación (tabla CRM persistida)."""

    __tablename__ = "investigation_leads"
    __table_args__ = (
        CheckConstraint("status IN ('nuevo','contactado','descartado','convertido')"),
        {"schema": "prod"},
    )

    lead_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prod.user_investigations.investigation_id", ondelete="CASCADE"),
        nullable=False,
    )
    denue_id: Mapped[str] = mapped_column(Text, nullable=False)
    cve_ent: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    idt: Mapped[float | None] = mapped_column(Numeric(5, 2))
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    score_components: Mapped[dict] = mapped_column(JSONB, nullable=False)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="nuevo")
    synced_to_crm_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
