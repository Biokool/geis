"""Sesión y motor de base de datos (PostgreSQL + PostGIS)."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

#: Motor síncrono (psycopg2). ``pool_pre_ping`` evita conexiones muertas.
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

#: Factoría de sesiones.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: provee una sesión por request y la cierra."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def safe_rollback(db) -> None:
    """Limpia la sesión tras un error SQL que el flujo decide tragarse.

    Sin esto, la sentencia fallida deja la transacción abortada y TODA
    sentencia posterior del request muere con el error secundario
    (psycopg2 ``InFailedSqlTransaction``) en lugar del error real.
    Best-effort: los fakes de tests no implementan ``rollback()``.
    """
    try:
        db.rollback()
    except Exception:  # noqa: BLE001 — limpiar no debe romper el flujo
        pass
