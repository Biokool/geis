"""Migración 0003 — módulo de configuración inicial + IA interna.

Crea:
- ``company_profiles``: versiones del documento PERFIL-EMPRESA.md
  (markdown crudo + frontmatter parseado en JSON; solo una activa).
- ``knowledge_facts``: hechos aprendidos por vertical (upsert por
  UNIQUE(vertical_id, fact_key)); origen 'manual' | 'system' | 'ai:{provider}'.
- ``ai_usage_log``: bitácora de cada uso de un proveedor de IA.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-19
"""
from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

DDL = """
-- 0003.1. Versiones del perfil de empresa (configuración inicial).
CREATE TABLE IF NOT EXISTS company_profiles (
    id          serial PRIMARY KEY,
    vertical_id text,
    nombre      text,
    profile_md  text,
    profile_json jsonb,
    version     integer NOT NULL DEFAULT 1,
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_company_profiles_active
    ON company_profiles (is_active) WHERE is_active;

-- 0003.2. Hechos de conocimiento por vertical (auto-aprendizaje).
CREATE TABLE IF NOT EXISTS knowledge_facts (
    id          serial PRIMARY KEY,
    vertical_id text NOT NULL,
    fact_key    text NOT NULL,
    fact_value  jsonb,
    source      text,
    confidence  numeric(3,2) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vertical_id, fact_key)
);
CREATE INDEX IF NOT EXISTS ix_knowledge_facts_vertical
    ON knowledge_facts (vertical_id);

-- 0003.3. Bitácora de uso de proveedores de IA.
CREATE TABLE IF NOT EXISTS ai_usage_log (
    id         serial PRIMARY KEY,
    provider   text,
    purpose    text,
    ok         boolean,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ai_usage_log_created
    ON ai_usage_log (created_at DESC);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_usage_log;")
    op.execute("DROP TABLE IF EXISTS knowledge_facts;")
    op.execute("DROP TABLE IF EXISTS company_profiles;")
