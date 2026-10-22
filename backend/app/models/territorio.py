"""Marco Geoestadístico y Censo (§5.2 del SRS): entidades, municipios, AGEB, manzanas."""
from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    CHAR,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarcoEntidad(Base):
    """Entidades federativas del Marco Geoestadístico."""

    __tablename__ = "marco_entidades"
    __table_args__ = {"schema": "prod"}

    cve_ent: Mapped[str] = mapped_column(CHAR(2), primary_key=True)
    nom_ent: Mapped[str] = mapped_column(Text, nullable=False)
    geom: Mapped[str] = mapped_column(Geometry("MULTIPOLYGON", 4326), nullable=False)
    edition_id: Mapped[int | None] = mapped_column(
        ForeignKey("prod.data_editions.edition_id")
    )


class MarcoMunicipio(Base):
    """Municipios / alcaldías del Marco Geoestadístico."""

    __tablename__ = "marco_municipios"
    __table_args__ = {"schema": "prod"}

    cvegeo: Mapped[str] = mapped_column(CHAR(5), primary_key=True)
    cve_ent: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    cve_mun: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    nom_mun: Mapped[str] = mapped_column(Text, nullable=False)
    geom: Mapped[str] = mapped_column(Geometry("MULTIPOLYGON", 4326), nullable=False)
    edition_id: Mapped[int | None] = mapped_column(
        ForeignKey("prod.data_editions.edition_id")
    )


class InegiAgeb(Base):
    """AGEB urbanas/rurales con variables sociodemográficas del Censo."""

    __tablename__ = "inegi_agebs"
    __table_args__ = {"schema": "prod"}

    cvegeo: Mapped[str] = mapped_column(Text, primary_key=True)
    cve_ent: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    cve_mun: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    cve_loc: Mapped[str] = mapped_column(Text, nullable=False)
    cve_ageb: Mapped[str] = mapped_column(Text, nullable=False)
    ambito: Mapped[str | None] = mapped_column(Text)

    pob_total: Mapped[int | None] = mapped_column(Integer)
    pob_femenina: Mapped[int | None] = mapped_column(Integer)
    pob_masculina: Mapped[int | None] = mapped_column(Integer)
    pob_0_14: Mapped[int | None] = mapped_column(Integer)
    pob_15_29: Mapped[int | None] = mapped_column(Integer)
    pob_30_59: Mapped[int | None] = mapped_column(Integer)
    pob_60_mas: Mapped[int | None] = mapped_column(Integer)
    pob_sin_clasificar: Mapped[int | None] = mapped_column(Integer)
    pea_ocupada: Mapped[int | None] = mapped_column(Integer)
    viv_habitadas: Mapped[int | None] = mapped_column(Integer)
    prom_ocupantes_viv: Mapped[float | None] = mapped_column(Numeric(4, 2))
    pct_viv_internet: Mapped[float | None] = mapped_column(Numeric(5, 2))
    pct_viv_computadora: Mapped[float | None] = mapped_column(Numeric(5, 2))
    pct_viv_automovil: Mapped[float | None] = mapped_column(Numeric(5, 2))
    pct_viv_celular: Mapped[float | None] = mapped_column(Numeric(5, 2))
    nse_score: Mapped[float | None] = mapped_column(Numeric(5, 3))
    nse_banda: Mapped[str | None] = mapped_column(Text)

    geom: Mapped[str] = mapped_column(Geometry("MULTIPOLYGON", 4326), nullable=False)
    edition_id: Mapped[int | None] = mapped_column(
        ForeignKey("prod.data_editions.edition_id")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InegiManzana(Base):
    """Manzanas del Marco Geoestadístico (variables heredadas del AGEB)."""

    __tablename__ = "inegi_manzanas"
    __table_args__ = {"schema": "prod"}

    cvegeo: Mapped[str] = mapped_column(Text, primary_key=True)
    cve_ageb: Mapped[str] = mapped_column(
        ForeignKey("prod.inegi_agebs.cvegeo"), nullable=False
    )
    pob_total: Mapped[int | None] = mapped_column(Integer)
    viv_habitadas: Mapped[int | None] = mapped_column(Integer)
    heredado_de_ageb: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    geom: Mapped[str] = mapped_column(Geometry("MULTIPOLYGON", 4326), nullable=False)
    edition_id: Mapped[int | None] = mapped_column(
        ForeignKey("prod.data_editions.edition_id")
    )
