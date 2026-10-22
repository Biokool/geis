"""Utilidades compartidas de los jobs ETL: argparse base, logging e idempotencia."""
from __future__ import annotations

import argparse
import logging
import sys


def base_parser(descripcion: str) -> argparse.ArgumentParser:
    """Parser común: --edition, --dry-run, --force, --log-level."""
    p = argparse.ArgumentParser(description=descripcion)
    p.add_argument("--edition", required=True, help="Edición a ingestar (p. ej. DENUE_11_2023)")
    p.add_argument("--dry-run", action="store_true", help="No escribe en la BD; solo reporta lo que haría")
    p.add_argument("--force", action="store_true", help="Reingesta aunque la edición ya exista")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


def configurar_logging(level: str) -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stdout,
    )
    return logging.getLogger("geis.etl")


def edicion_ya_ingestada(session, source_code: str, edition: str) -> bool:
    """Idempotencia por edición: True si la edición ya fue ingerida."""
    from sqlalchemy import text

    row = session.execute(
        text(
            "SELECT 1 FROM prod.data_editions e "
            "JOIN prod.data_sources s ON s.source_id = e.source_id "
            "WHERE s.code = :code AND e.edition = :edition"
        ),
        {"code": source_code, "edition": edition},
    ).first()
    return row is not None
