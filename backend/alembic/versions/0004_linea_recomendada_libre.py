"""Migración 0004 — relaja el CHECK de prod.leads.linea_recomendada.

Contexto: la migración 0002 limitó ``linea_recomendada`` a
('koolkat','solar','evaporativa'). Con el módulo de configuración inicial
(0003), ``linea_recomendada()`` puede devolver nombres de producto del
perfil de la empresa (ej. "Membresía mensual" para una cadena de
gimnasios); persistirlos violaría el CHECK. La validación de valores
válidos pasa a la capa de aplicación (``derive`` + ``line_rules``);
la columna queda como texto libre.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # El nombre del CHECK es autogenerado por Postgres; se localiza y elimina.
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'prod.leads'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%linea_recomendada%IN%'
            """
        )
    ).fetchone()
    if row:
        op.execute(sa.text(f'ALTER TABLE prod.leads DROP CONSTRAINT "{row[0]}"'))


def downgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE prod.leads ADD CONSTRAINT leads_linea_chk "
            "CHECK (linea_recomendada IN ('koolkat','solar','evaporativa'))"
        )
    )
