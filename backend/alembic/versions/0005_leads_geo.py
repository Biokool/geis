"""Migración 0005 — columnas geográficas derivadas en prod.leads.

Contexto (ARQUITECTURA-2-SECCIONES §3 + INVENTARIO-RADAR §2.3): el Radar
original NO tiene campos estructurados de entidad/municipio/colonia/CP/
SCIAN; los filtros geográficos de la Sección 2 se derivan. Esta migración
agrega las 5 columnas (nullable) a ``prod.leads``; las llena
``POST /api/v1/leads/enrich-geo`` (join espacial con AGEBs + DENUE más
cercano ≤500 m, o regex de CP sobre la dirección sin geometría).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-21
"""
from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

DDL = """
ALTER TABLE prod.leads ADD COLUMN IF NOT EXISTS entidad   VARCHAR;
ALTER TABLE prod.leads ADD COLUMN IF NOT EXISTS municipio VARCHAR;
ALTER TABLE prod.leads ADD COLUMN IF NOT EXISTS colonia   VARCHAR;
ALTER TABLE prod.leads ADD COLUMN IF NOT EXISTS cp        VARCHAR(5);
ALTER TABLE prod.leads ADD COLUMN IF NOT EXISTS scian     VARCHAR(6);

CREATE INDEX IF NOT EXISTS ix_leads_entidad   ON prod.leads (entidad);
CREATE INDEX IF NOT EXISTS ix_leads_municipio ON prod.leads (municipio);
CREATE INDEX IF NOT EXISTS ix_leads_colonia   ON prod.leads (colonia);
CREATE INDEX IF NOT EXISTS ix_leads_cp        ON prod.leads (cp);
CREATE INDEX IF NOT EXISTS ix_leads_scian     ON prod.leads (scian);
CREATE INDEX IF NOT EXISTS ix_leads_geo_cascada
    ON prod.leads (entidad, municipio, colonia);
"""

DOWNGRADE_DDL = """
DROP INDEX IF EXISTS prod.ix_leads_geo_cascada;
DROP INDEX IF EXISTS prod.ix_leads_scian;
DROP INDEX IF EXISTS prod.ix_leads_cp;
DROP INDEX IF EXISTS prod.ix_leads_colonia;
DROP INDEX IF EXISTS prod.ix_leads_municipio;
DROP INDEX IF EXISTS prod.ix_leads_entidad;

ALTER TABLE prod.leads DROP COLUMN IF EXISTS scian;
ALTER TABLE prod.leads DROP COLUMN IF EXISTS cp;
ALTER TABLE prod.leads DROP COLUMN IF EXISTS colonia;
ALTER TABLE prod.leads DROP COLUMN IF EXISTS municipio;
ALTER TABLE prod.leads DROP COLUMN IF EXISTS entidad;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(DOWNGRADE_DDL)
