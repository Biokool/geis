"""Migración 0006 — compartir reportes + ganadora persistente (Sección 1).

- Tabla ``prod.report_shares``: tokens opacos expirables/revocables para
  ver un reporte en modo invitado (``/r/{token}``, solo lectura).
- Columna ``es_principal`` en ``prod.user_investigations``: la ganadora
  del comparador persiste (antes era marca de sesión en el frontend).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_shares",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["report_id"], ["prod.reports.report_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
        schema="prod",
    )
    op.create_index(
        "ix_report_shares_report_id", "report_shares", ["report_id"],
        schema="prod",
    )
    op.add_column(
        "user_investigations",
        sa.Column(
            "es_principal", sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
        schema="prod",
    )


def downgrade() -> None:
    op.drop_column("user_investigations", "es_principal", schema="prod")
    op.drop_index("ix_report_shares_report_id", table_name="report_shares", schema="prod")
    op.drop_table("report_shares", schema="prod")
