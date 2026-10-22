"""Configuración central de la API GEIS.

Lee todo desde variables de entorno (sin secretos en código).
Implementado con pydantic v2 + os.getenv para no depender de
``pydantic-settings``.
"""
from __future__ import annotations

import os

from pydantic import BaseModel


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


class Settings(BaseModel):
    """Parámetros de la aplicación leídos del entorno."""

    app_name: str = "GEIS API"
    app_version: str = _env("APP_VERSION", "1.0.0")
    environment: str = _env("ENVIRONMENT", "development")
    debug: bool = _env("DEBUG", "false").lower() in ("1", "true", "yes")

    # Base de datos (PostgreSQL + PostGIS)
    database_url: str = _env(
        "DATABASE_URL",
        "postgresql+psycopg2://geis:geis@localhost:5432/geis",
    )

    # Redis (rate limiting / caché; opcional en dev)
    redis_url: str = _env("REDIS_URL", "")

    # Conector DENUE (API del INEGI). Si está vacío, el conector opera en
    # modo stub con datos de muestra deterministas.
    denue_api_token: str = _env("DENUE_API_TOKEN", "")
    denue_api_base_url: str = _env(
        "DENUE_API_BASE_URL",
        "https://www.inegi.org.mx/app/api/denue/v1/consulta",
    )
    denue_api_timeout_s: float = float(_env("DENUE_API_TIMEOUT_S", "20"))

    # Seguridad
    secret_key: str = _env("SECRET_KEY", "dev-only-insecure-secret-key")

    # Versión de los modelos analíticos (ISM/Huff/TAM/IDT/scoring) usada en
    # el linaje de cada respuesta.
    model_version: str = _env("MODEL_VERSION", "1.0.0")

    # Ecosistema GEIS × Radar: servicios externos (sobrescribibles por env).
    n8n_url: str = _env("N8N_URL", "http://n8n:5678")
    n8n_api_key: str = _env("N8N_API_KEY", "")
    scraper_url: str = _env("SCRAPER_URL", "http://scraper:5000")

    # LinkedIn OAuth (app real con Community Management API). Vacías =
    # integración no configurada (los endpoints devuelven 501 documentado).
    linkedin_client_id: str = _env("LINKEDIN_CLIENT_ID", "")
    linkedin_client_secret: str = _env("LINKEDIN_CLIENT_SECRET", "")
    linkedin_redirect_uri: str = _env("LINKEDIN_REDIRECT_URI", "")
    linkedin_access_token: str = _env("LINKEDIN_ACCESS_TOKEN", "")

    @property
    def is_dev(self) -> bool:
        return self.environment.lower() in ("development", "dev", "local")


settings = Settings()
