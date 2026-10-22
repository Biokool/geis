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
