"""Salud del ecosistema: semáforo postgres/n8n/scraper + resumen de providers."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.radar import SystemHealth

router = APIRouter(prefix="/system", tags=["system"])

#: URLs por defecto de los servicios del compose (sobrescribibles por env).
N8N_URL_DEFAULT = "http://n8n:5678"
SCRAPER_URL_DEFAULT = "http://scraper:5000"


def _servicio_ok(url: str) -> str:
    """'ok' si el servicio responde en 2s, 'error' si no."""
    try:
        resp = httpx.get(url, timeout=2.0)
        return "ok" if resp.status_code < 500 else "error"
    except Exception:
        return "error"


def _resumen_providers(db: Session) -> dict[str, dict]:
    """{name: {mode, enabled}}; vacío si la tabla aún no existe."""
    try:
        filas = db.execute(text("SELECT name, mode, enabled FROM prod.providers")).all()
        return {f[0]: {"mode": f[1], "enabled": f[2]} for f in filas}
    except Exception:
        return {}


@router.get("/health", response_model=SystemHealth)
def health(db: Session = Depends(get_db)):
    """Semáforo del ecosistema: postgres, n8n, scraper y providers."""
    try:
        db.execute(text("SELECT 1"))
        postgres = "ok"
    except Exception:
        postgres = "error"

    n8n_url = os.getenv("N8N_URL", N8N_URL_DEFAULT)
    scraper_url = os.getenv("SCRAPER_URL", SCRAPER_URL_DEFAULT)

    return SystemHealth(
        postgres=postgres,
        n8n=_servicio_ok(f"{n8n_url}/healthz"),
        scraper=_servicio_ok(f"{scraper_url}/health"),
        providers=_resumen_providers(db),
    )
