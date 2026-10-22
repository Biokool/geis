"""DENUE: establecimientos (particionada por cve_ent) e historial entre ediciones (§5.3–5.4)."""
from __future__ import annotations

from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DenueEstablishment(Base):
    """Establecimiento del DENUE. Tabla particionada por LISTA (cve_ent)."""

    __tablename__ = "denue_establishments"
    __table_args__ = (
        CheckConstraint("estrato_ordinal BETWEEN 1 AND 7"),
        {
            "schema": "prod",
            "postgresql_partition_by": "LIST (cve_ent)",
        },
    )

    denue_id: Mapped[str] = mapped_column(Text, primary_key=True)
    clee: Mapped[str | None] = mapped_column(Text)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    razon_social: Mapped[str | None] = mapped_column(Text)
    scian_code: Mapped[str] = mapped_column(CHAR(6), nullable=False)
    scian_desc: Mapped[str | None] = mapped_column(Text)
    estrato_texto: Mapped[str] = mapped_column(Text, nullable=False)
    estrato_ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tipo_vialidad: Mapped[str | None] = mapped_column(Text)
    nom_vialidad: Mapped[str | None] = mapped_column(Text)
    num_exterior: Mapped[str | None] = mapped_column(Text)
    num_interior: Mapped[str | None] = mapped_column(Text)
    colonia: Mapped[str | None] = mapped_column(Text)
    cp: Mapped[str | None] = mapped_column(CHAR(5))
    cve_ent: Mapped[str] = mapped_column(CHAR(2), primary_key=True)
    entidad: Mapped[str | None] = mapped_column(Text)
    cve_mun: Mapped[str | None] = mapped_column(CHAR(3))
    municipio: Mapped[str | None] = mapped_column(Text)
    localidad: Mapped[str | None] = mapped_column(Text)
    cve_ageb: Mapped[str | None] = mapped_column(Text)
    cve_manzana: Mapped[str | None] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(Text)
    correo: Mapped[str | None] = mapped_column(Text)
    sitio_web: Mapped[str | None] = mapped_column(Text)
    tipo_unidad: Mapped[str | None] = mapped_column(Text)
    tipo_establecimiento: Mapped[str | None] = mapped_column(Text)
    fecha_alta: Mapped[date | None] = mapped_column(Date)
    lat: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    lon: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    geom: Mapped[str] = mapped_column(Geometry("POINT", 4326), nullable=False)
    edition_id: Mapped[int] = mapped_column(
        ForeignKey("prod.data_editions.edition_id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DenueHistory(Base):
    """Cambios detectados del DENUE entre ediciones (§7.3 del SRS)."""

    __tablename__ = "denue_history"
    __table_args__ = (
        CheckConstraint(
            "change_type IN ('alta','baja','cambio_estrato','cambio_scian',"
            "'cambio_domicilio','reactivacion')"
        ),
        {"schema": "prod"},
    )

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    denue_id: Mapped[str] = mapped_column(Text, nullable=False)
    cve_ent: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    edition_from: Mapped[str] = mapped_column(Text, nullable=False)
    edition_to: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
