"""Migración inicial GEIS — DDL maestro del SRS §5.

Crea: extensiones, esquemas prod/stg/quarantine, catálogos y linaje,
Marco Geoestadístico, DENUE particionada por cve_ent (32 particiones),
historial, investigaciones, leads, agregados, auditoría, tabla de
reportes, triggers de updated_at y la vista v_municipio_kpis.

Revision ID: 0001
Revises:
Create Date: 2026-10-18
"""
from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DDL = """
-- 0. Extensiones y esquemas
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE SCHEMA IF NOT EXISTS prod;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS quarantine;

-- 1. Catálogos y fuentes (linaje de datos)
CREATE TABLE IF NOT EXISTS prod.data_sources (
    source_id       serial PRIMARY KEY,
    code            text NOT NULL UNIQUE,
    name            text NOT NULL,
    provider        text NOT NULL,
    license         text,
    url             text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prod.data_editions (
    edition_id      serial PRIMARY KEY,
    source_id       int NOT NULL REFERENCES prod.data_sources(source_id),
    edition         text NOT NULL,
    published_at    date,
    ingested_at     timestamptz NOT NULL DEFAULT now(),
    records_total   bigint,
    records_valid   bigint,
    records_quarantine bigint,
    notes           text,
    UNIQUE (source_id, edition)
);

CREATE TABLE IF NOT EXISTS prod.cat_scian (
    scian_code      char(6) PRIMARY KEY,
    description     text NOT NULL,
    scian_version   text NOT NULL DEFAULT '2023',
    sector_code     char(2) NOT NULL,
    thermal_intensity numeric(3,2) NOT NULL DEFAULT 0.50 CHECK (thermal_intensity BETWEEN 0 AND 1),
    base_attractiveness numeric(3,2) NOT NULL DEFAULT 0.50 CHECK (base_attractiveness BETWEEN 0 AND 1),
    lambda_default  numeric(4,2) NOT NULL DEFAULT 2.00,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_cat_scian_sector ON prod.cat_scian (sector_code);

CREATE TABLE IF NOT EXISTS prod.cat_giro_scian (
    giro_id         serial PRIMARY KEY,
    giro_label      text NOT NULL,
    scian_code      char(6) NOT NULL REFERENCES prod.cat_scian(scian_code),
    confidence      numeric(3,2) NOT NULL DEFAULT 1.00,
    UNIQUE (giro_label, scian_code)
);
CREATE INDEX IF NOT EXISTS ix_giro_label_trgm ON prod.cat_giro_scian USING gin (giro_label gin_trgm_ops);

CREATE TABLE IF NOT EXISTS prod.model_params (
    param_id        serial PRIMARY KEY,
    vertical        text NOT NULL,
    model           text NOT NULL,
    params          jsonb NOT NULL,
    version         int NOT NULL DEFAULT 1,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vertical, model, version)
);

-- 2. Marco Geoestadístico
CREATE TABLE IF NOT EXISTS prod.marco_entidades (
    cve_ent         char(2) PRIMARY KEY,
    nom_ent         text NOT NULL,
    geom            geometry(MultiPolygon, 4326) NOT NULL,
    edition_id      int REFERENCES prod.data_editions(edition_id)
);
CREATE INDEX IF NOT EXISTS ix_marco_ent_geom ON prod.marco_entidades USING gist (geom);

CREATE TABLE IF NOT EXISTS prod.marco_municipios (
    cvegeo          char(5) PRIMARY KEY,
    cve_ent         char(2) NOT NULL,
    cve_mun         char(3) NOT NULL,
    nom_mun         text NOT NULL,
    geom            geometry(MultiPolygon, 4326) NOT NULL,
    edition_id      int REFERENCES prod.data_editions(edition_id)
);
CREATE INDEX IF NOT EXISTS ix_marco_mun_geom ON prod.marco_municipios USING gist (geom);
CREATE INDEX IF NOT EXISTS ix_marco_mun_ent ON prod.marco_municipios (cve_ent);

CREATE TABLE IF NOT EXISTS prod.inegi_agebs (
    cvegeo          text PRIMARY KEY,
    cve_ent         char(2) NOT NULL,
    cve_mun         char(3) NOT NULL,
    cve_loc         text NOT NULL,
    cve_ageb        text NOT NULL,
    ambito          text,
    pob_total       integer,
    pob_femenina    integer,
    pob_masculina   integer,
    pob_0_14        integer,
    pob_15_29       integer,
    pob_30_59       integer,
    pob_60_mas      integer,
    pob_sin_clasificar integer,
    pea_ocupada     integer,
    viv_habitadas   integer,
    prom_ocupantes_viv numeric(4,2),
    pct_viv_internet    numeric(5,2),
    pct_viv_computadora numeric(5,2),
    pct_viv_automovil   numeric(5,2),
    pct_viv_celular     numeric(5,2),
    nse_score       numeric(5,3),
    nse_banda       text,
    geom            geometry(MultiPolygon, 4326) NOT NULL,
    edition_id      int REFERENCES prod.data_editions(edition_id),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ageb_geom ON prod.inegi_agebs USING gist (geom);
CREATE INDEX IF NOT EXISTS ix_ageb_ent_mun ON prod.inegi_agebs (cve_ent, cve_mun);
CREATE INDEX IF NOT EXISTS ix_ageb_nse ON prod.inegi_agebs (nse_banda);

CREATE TABLE IF NOT EXISTS prod.inegi_manzanas (
    cvegeo          text PRIMARY KEY,
    cve_ageb        text NOT NULL REFERENCES prod.inegi_agebs(cvegeo),
    pob_total       integer,
    viv_habitadas   integer,
    heredado_de_ageb boolean NOT NULL DEFAULT false,
    geom            geometry(MultiPolygon, 4326) NOT NULL,
    edition_id      int REFERENCES prod.data_editions(edition_id)
);
CREATE INDEX IF NOT EXISTS ix_manz_geom ON prod.inegi_manzanas USING gist (geom);
CREATE INDEX IF NOT EXISTS ix_manz_ageb ON prod.inegi_manzanas (cve_ageb);

-- 3. DENUE — establecimientos (particionada por entidad)
CREATE TABLE IF NOT EXISTS prod.denue_establishments (
    denue_id        text NOT NULL,
    clee            text,
    nombre          text NOT NULL,
    razon_social    text,
    scian_code      char(6) NOT NULL,
    scian_desc      text,
    estrato_texto   text NOT NULL,
    estrato_ordinal smallint NOT NULL CHECK (estrato_ordinal BETWEEN 1 AND 7),
    tipo_vialidad   text,
    nom_vialidad    text,
    num_exterior    text,
    num_interior    text,
    colonia         text,
    cp              char(5),
    cve_ent         char(2) NOT NULL,
    entidad         text,
    cve_mun         char(3),
    municipio       text,
    localidad       text,
    cve_ageb        text,
    cve_manzana     text,
    telefono        text,
    correo          text,
    sitio_web       text,
    tipo_unidad     text,
    tipo_establecimiento text,
    fecha_alta      date,
    lat             numeric(9,6) NOT NULL,
    lon             numeric(9,6) NOT NULL,
    geom            geometry(Point, 4326) NOT NULL,
    edition_id      int NOT NULL REFERENCES prod.data_editions(edition_id),
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (denue_id, cve_ent)
) PARTITION BY LIST (cve_ent);

DO $$
DECLARE e text;
BEGIN
  FOR e IN SELECT lpad(g::text, 2, '0') FROM generate_series(1,32) g LOOP
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS prod.denue_est_p%s PARTITION OF prod.denue_establishments FOR VALUES IN (%L)',
      e, e);
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS ix_denue_p%s_geom ON prod.denue_est_p%s USING gist (geom)',
      e, e);
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS ix_denue_p%s_scian ON prod.denue_est_p%s (scian_code, estrato_ordinal)',
      e, e);
  END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS ix_denue_nombre_trgm ON prod.denue_establishments USING gin (nombre gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_denue_clee ON prod.denue_establishments (clee) WHERE clee IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_denue_ageb ON prod.denue_establishments (cve_ageb) WHERE cve_ageb IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_denue_edition ON prod.denue_establishments (edition_id);

-- 4. Historial / auditoría del DENUE entre ediciones
CREATE TABLE IF NOT EXISTS prod.denue_history (
    history_id      bigserial PRIMARY KEY,
    denue_id        text NOT NULL,
    cve_ent         char(2) NOT NULL,
    edition_from    text NOT NULL,
    edition_to      text NOT NULL,
    change_type     text NOT NULL CHECK (change_type IN ('alta','baja','cambio_estrato','cambio_scian','cambio_domicilio','reactivacion')),
    old_values      jsonb,
    new_values      jsonb,
    detected_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_denh_denue ON prod.denue_history (denue_id);
CREATE INDEX IF NOT EXISTS ix_denh_type ON prod.denue_history (change_type);
CREATE INDEX IF NOT EXISTS ix_denh_editions ON prod.denue_history (edition_from, edition_to);

-- 5. Investigaciones de usuarios y leads
CREATE TABLE IF NOT EXISTS prod.user_investigations (
    investigation_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         text NOT NULL,
    title           text NOT NULL,
    investigation_type text NOT NULL CHECK (investigation_type IN
                        ('location_viability','b2b_prospecting','lookalike','multi_compare','real_estate')),
    vertical        text,
    territory_geojson geometry(Geometry, 4326),
    territory_kind  text NOT NULL CHECK (territory_kind IN ('point_buffers','isochrone','polygon','ageb','municipality','state')),
    center_lat      numeric(9,6),
    center_lon      numeric(9,6),
    radii_m         integer[],
    isochrone_min   integer[],
    params          jsonb NOT NULL,
    params_version  int NOT NULL DEFAULT 1,
    scores          jsonb,
    verdict         text CHECK (verdict IN ('AVANZAR','NEGOCIAR','EXPLORAR_OTRA_ZONA')),
    status          text NOT NULL DEFAULT 'completed' CHECK (status IN ('running','completed','failed')),
    edition_id      int REFERENCES prod.data_editions(edition_id),
    model_params_version int,
    report_id       uuid,
    is_public       boolean NOT NULL DEFAULT false,
    share_token     text UNIQUE,
    share_expires_at timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_inv_user ON prod.user_investigations (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_inv_terr ON prod.user_investigations USING gist (territory_geojson);
CREATE INDEX IF NOT EXISTS ix_inv_type ON prod.user_investigations (investigation_type);
CREATE INDEX IF NOT EXISTS ix_inv_verdict ON prod.user_investigations (verdict) WHERE verdict IS NOT NULL;

CREATE TABLE IF NOT EXISTS prod.investigation_leads (
    lead_id         bigserial PRIMARY KEY,
    investigation_id uuid NOT NULL REFERENCES prod.user_investigations(investigation_id) ON DELETE CASCADE,
    denue_id        text NOT NULL,
    cve_ent         char(2) NOT NULL,
    idt             numeric(5,2),
    score           numeric(5,2) NOT NULL,
    score_components jsonb NOT NULL,
    distance_m      integer,
    status          text NOT NULL DEFAULT 'nuevo' CHECK (status IN ('nuevo','contactado','descartado','convertido')),
    synced_to_crm_at timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (investigation_id, denue_id)
);
CREATE INDEX IF NOT EXISTS ix_leads_inv_score ON prod.investigation_leads (investigation_id, score DESC);
CREATE INDEX IF NOT EXISTS ix_leads_denue ON prod.investigation_leads (denue_id, cve_ent);

-- 5b. Reportes de ubicación persistidos (JSON de 13 secciones + veredicto)
CREATE TABLE IF NOT EXISTS prod.reports (
    report_id       uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id uuid REFERENCES prod.user_investigations(investigation_id) ON DELETE SET NULL,
    title           text NOT NULL,
    verdict         text,
    payload         jsonb NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_reports_inv ON prod.reports (investigation_id);

-- 6. Agregados precalculados
CREATE TABLE IF NOT EXISTS prod.agg_ageb_scian (
    cvegeo          text NOT NULL REFERENCES prod.inegi_agebs(cvegeo),
    scian_code      char(6) NOT NULL,
    estrato_ordinal smallint NOT NULL,
    n               integer NOT NULL,
    edition_id      int REFERENCES prod.data_editions(edition_id),
    PRIMARY KEY (cvegeo, scian_code, estrato_ordinal)
);

CREATE TABLE IF NOT EXISTS prod.agg_hex_h3 (
    h3_index        text PRIMARY KEY,
    resolution      smallint NOT NULL,
    n_establishments integer NOT NULL DEFAULT 0,
    idt_avg         numeric(5,2),
    pob_total       integer,
    geom            geometry(Polygon, 4326) NOT NULL,
    edition_id      int REFERENCES prod.data_editions(edition_id)
);
CREATE INDEX IF NOT EXISTS ix_hex_geom ON prod.agg_hex_h3 USING gist (geom);

-- 7. Auditoría genérica (append-only)
CREATE TABLE IF NOT EXISTS prod.audit_log (
    audit_id        bigserial PRIMARY KEY,
    actor           text NOT NULL,
    action          text NOT NULL,
    entity          text NOT NULL,
    entity_id       text,
    details         jsonb,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_actor ON prod.audit_log (actor, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_entity ON prod.audit_log (entity, entity_id);

-- 8. Triggers de updated_at
CREATE OR REPLACE FUNCTION prod.touch_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END $$ LANGUAGE plpgsql;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['prod.denue_establishments','prod.inegi_agebs',
                           'prod.user_investigations','prod.cat_scian'] LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS trg_touch ON %s', t);
    EXECUTE format('CREATE TRIGGER trg_touch BEFORE UPDATE ON %s
                    FOR EACH ROW EXECUTE FUNCTION prod.touch_updated_at()', t);
  END LOOP;
END $$;

-- 9. Vista de conveniencia: KPIs por municipio
CREATE OR REPLACE VIEW prod.v_municipio_kpis AS
SELECT m.cvegeo, m.nom_mun, m.cve_ent,
       COUNT(d.denue_id) AS n_establecimientos,
       COUNT(*) FILTER (WHERE d.estrato_ordinal >= 5) AS n_industriales_50plus
FROM prod.marco_municipios m
LEFT JOIN prod.denue_establishments d
       ON ST_Within(d.geom, m.geom) AND d.is_active
GROUP BY m.cvegeo, m.nom_mun, m.cve_ent;
"""

DOWNGRADE_DDL = """
DROP VIEW IF EXISTS prod.v_municipio_kpis;
DROP TABLE IF EXISTS prod.audit_log;
DROP TABLE IF EXISTS prod.agg_hex_h3;
DROP TABLE IF EXISTS prod.agg_ageb_scian;
DROP TABLE IF EXISTS prod.reports;
DROP TABLE IF EXISTS prod.investigation_leads;
DROP TABLE IF EXISTS prod.user_investigations;
DROP TABLE IF EXISTS prod.denue_history;
DROP TABLE IF EXISTS prod.denue_establishments CASCADE;
DROP TABLE IF EXISTS prod.inegi_manzanas;
DROP TABLE IF EXISTS prod.inegi_agebs;
DROP TABLE IF EXISTS prod.marco_municipios;
DROP TABLE IF EXISTS prod.marco_entidades;
DROP TABLE IF EXISTS prod.model_params;
DROP TABLE IF EXISTS prod.cat_giro_scian;
DROP TABLE IF EXISTS prod.cat_scian;
DROP TABLE IF EXISTS prod.data_editions;
DROP TABLE IF EXISTS prod.data_sources;
DROP FUNCTION IF EXISTS prod.touch_updated_at() CASCADE;
DROP SCHEMA IF EXISTS quarantine;
DROP SCHEMA IF EXISTS stg;
DROP SCHEMA IF EXISTS prod CASCADE;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute(DOWNGRADE_DDL)
