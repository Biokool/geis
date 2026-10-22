"""Agregados precalculados (§5.6 del SRS) para rendimiento (RNF-001)."""
from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import (
    CHAR,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AggAgebScian(Base):
    """Conteo de establecimientos por AGEB × clase SCIAN × estrato."""

    __tablename__ = "agg_ageb_scian"
    __table_args__ = {"schema": "prod"}

    cvegeo: Mapped[str] = mapped_column(
        ForeignKey("prod.inegi_agebs.cvegeo"), primary_key=True
    )
    scian_code: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    estrato_ordinal: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    edition_id: Mapped[int | None] = mapped_column(
        ForeignKey("prod.data_editions.edition_id")
    )


class AggHexH3(Base):
    """Agregados por hexágono H3 (resolución 8/9) para mapas de calor."""

    __tablename__ = "agg_hex_h3"
    __table_args__ = {"schema": "prod"}

    h3_index: Mapped[str] = mapped_column(Text, primary_key=True)
    resolution: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    n_establishments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idt_avg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    pob_total: Mapped[int | None] = mapped_column(Integer)
    geom: Mapped[str] = mapped_column(Geometry("POLYGON", 4326), nullable=False)
    edition_id: Mapped[int | None] = mapped_column(
        ForeignKey("prod.data_editions.edition_id")
    )
