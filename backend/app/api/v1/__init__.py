"""Routers de la API v1."""
from app.api.v1 import (
    ai,
    analysis,
    catalogs,
    company,
    etl,
    geo_weather,
    investigations,
    leads,
    pipelines,
    proposals,
    providers,
    reports,
    signals,
    system,
    territories,
)
from app.api.v1.integrations import linkedin

__all__ = [
    "ai",
    "analysis",
    "catalogs",
    "company",
    "etl",
    "geo_weather",
    "investigations",
    "leads",
    "linkedin",
    "pipelines",
    "proposals",
    "providers",
    "reports",
    "signals",
    "system",
    "territories",
]
