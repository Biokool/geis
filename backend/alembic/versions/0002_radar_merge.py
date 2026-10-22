"""Fusión GEIS × Biokool Radar — DDL del ecosistema (§4 del blueprint).

Crea: prod.leads (base curada con etapa comercial y scoring unificado),
stg.leads_raw (staging del scraper), prod.runs (bitácora de pipelines
con bloqueo por orden), prod.providers (capa anti-cautiverio),
prod.proposals, prod.warm_signals y prod.linkedin_stats.

Backfill: migra prod.investigation_leads (GEIS) a prod.leads con
source='denue', conservando investigation_id y mapeando
status → etapa ('contactado'→'contactado', 'convertido'→'ganado',
'descartado'→'perdido', 'nuevo'→'nuevo').

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-19
"""
from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

DDL = """
-- 4.1. Leads unificada: converge investigation_leads (GEIS) + leads (Radar).
CREATE TABLE IF NOT EXISTS prod.leads (
    lead_id            bigserial PRIMARY KEY,
    source             text NOT NULL CHECK (source IN ('denue','gmaps','manual','linkedin')),
    denue_id           text,
    cve_ent            char(2),
    investigation_id   uuid REFERENCES prod.user_investigations(investigation_id) ON DELETE SET NULL,
    nombre             text NOT NULL,
    giro               text,
    direccion          text DEFAULT '',
    geom               geometry(Point, 4326),
    telefono           text,
    web                text,
    rating             numeric(3,2),
    empleados_est      smallint,
    score              numeric(5,2) NOT NULL DEFAULT 0,
    score_components   jsonb NOT NULL DEFAULT '{}',
    linea_recomendada  text CHECK (linea_recomendada IN ('koolkat','solar','evaporativa')),
    etapa              text NOT NULL DEFAULT 'nuevo'
                       CHECK (etapa IN ('nuevo','contactado','reunion','propuesta','ganado','perdido')),
    temp_zona          numeric(4,1),
    notas              text DEFAULT '',
    enriquecido_apollo boolean NOT NULL DEFAULT false,
    crm_synced_at      timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source, nombre, direccion)
);
CREATE INDEX IF NOT EXISTS ix_leads_geom ON prod.leads USING gist (geom);
CREATE INDEX IF NOT EXISTS ix_leads_etapa ON prod.leads (etapa);
CREATE INDEX IF NOT EXISTS ix_leads_score ON prod.leads (score DESC);

-- 4.2. Staging del scraper (antes leads_raw)
CREATE TABLE IF NOT EXISTS stg.leads_raw (
    raw_id     bigserial PRIMARY KEY,
    nombre     text, giro text, direccion text,
    geom       geometry(Point, 4326),
    telefono   text, web text, rating numeric(3,2),
    fuente     text DEFAULT 'google_maps', query text,
    procesado  boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);

-- 4.3. Bitácora de pipelines (runs) — sirve a n8n Y al ETL GEIS
CREATE TABLE IF NOT EXISTS prod.runs (
    run_id     bigserial PRIMARY KEY,
    pipeline   text NOT NULL,
    estado     text NOT NULL CHECK (estado IN ('running','ok','error')),
    detalle    jsonb,
    started_at timestamptz DEFAULT now(),
    finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS ix_runs_pipe ON prod.runs (pipeline, started_at DESC);

-- 4.4. Providers anti-cautiverio
CREATE TABLE IF NOT EXISTS prod.providers (
    name       text PRIMARY KEY,
    kind       text NOT NULL,
    mode       text NOT NULL DEFAULT 'local' CHECK (mode IN ('local','cloud','disabled')),
    provider   text NOT NULL DEFAULT 'local',
    config     jsonb NOT NULL DEFAULT '{}',
    enabled    boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- 4.5. Propuestas, señales cálidas, LinkedIn (adopción directa de Radar)
CREATE TABLE IF NOT EXISTS prod.proposals (
    proposal_id bigserial PRIMARY KEY,
    lead_id     bigint NOT NULL REFERENCES prod.leads(lead_id) ON DELETE CASCADE,
    titulo      text, linea text, monto numeric(12,2),
    estado      text NOT NULL DEFAULT 'borrador', created_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS prod.warm_signals (
    signal_id   bigserial PRIMARY KEY,
    fuente      text NOT NULL DEFAULT 'linkedin',
    titulo      text, detalle text, empresa_ref text,
    procesada   boolean DEFAULT false, created_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS prod.linkedin_stats (
    stat_id serial PRIMARY KEY, org_id text, followers int,
    posts_count int, engagement_total int, stats_date date DEFAULT CURRENT_DATE,
    raw jsonb, created_at timestamptz DEFAULT now(), UNIQUE (org_id, stats_date)
);

-- Trigger updated_at para las nuevas tablas con esa columna.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['prod.leads','prod.providers'] LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS trg_touch ON %s', t);
    EXECUTE format('CREATE TRIGGER trg_touch BEFORE UPDATE ON %s
                    FOR EACH ROW EXECUTE FUNCTION prod.touch_updated_at()', t);
  END LOOP;
END $$;

-- 4.6. Backfill: investigation_leads (GEIS) → prod.leads con source='denue'.
--      Idempotente por el UNIQUE (source, nombre, direccion).
INSERT INTO prod.leads
    (source, denue_id, cve_ent, investigation_id, nombre, giro, direccion,
     geom, telefono, web, score, score_components, etapa, crm_synced_at)
SELECT 'denue', il.denue_id, il.cve_ent, il.investigation_id, d.nombre,
       d.scian_desc,
       COALESCE(d.colonia,'') || ' ' || COALESCE(d.municipio,''),
       d.geom, d.telefono, d.sitio_web, il.score, il.score_components,
       CASE il.status
           WHEN 'contactado' THEN 'contactado'
           WHEN 'convertido'  THEN 'ganado'
           WHEN 'descartado'  THEN 'perdido'
           ELSE 'nuevo'
       END,
       il.synced_to_crm_at
FROM prod.investigation_leads il
JOIN prod.denue_establishments d
  ON d.denue_id = il.denue_id AND d.cve_ent = il.cve_ent
ON CONFLICT (source, nombre, direccion) DO NOTHING;
"""

DOWNGRADE_DDL = """
DROP TABLE IF EXISTS prod.linkedin_stats;
DROP TABLE IF EXISTS prod.warm_signals;
DROP TABLE IF EXISTS prod.proposals;
DROP TABLE IF EXISTS prod.providers;
DROP TABLE IF EXISTS prod.runs;
DROP TABLE IF EXISTS stg.leads_raw;
DROP TABLE IF EXISTS prod.leads;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(DOWNGRADE_DDL)
