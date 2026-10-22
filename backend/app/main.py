"""GEIS API — punto de entrada FastAPI."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

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
from app.core.config import settings
from app.db.session import SessionLocal

app = FastAPI(
    title="GEIS API",
    description="GeoEnterprise Intelligence System — geomarketing open source para México",
    version=settings.app_version,
)

# CORS abierto en desarrollo; restringir en producción vía ENVIRONMENT.
if settings.is_dev:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(territories.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(leads.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(investigations.router, prefix="/api/v1")
app.include_router(catalogs.router, prefix="/api/v1")
app.include_router(etl.router, prefix="/api/v1")
# Fusión GEIS × Biokool Radar (módulo de ejecución).
app.include_router(pipelines.router, prefix="/api/v1")
app.include_router(providers.router, prefix="/api/v1")
app.include_router(signals.router, prefix="/api/v1")
app.include_router(proposals.router, prefix="/api/v1")
app.include_router(geo_weather.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(linkedin.router, prefix="/api/v1")
# Configuración inicial + IA interna.
app.include_router(company.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness: la API responde."""
    return {"status": "ok", "service": "geis-api", "version": settings.app_version}


@app.get("/ready", tags=["ops"])
def ready() -> dict:
    """Readiness: verifica conectividad con la base de datos."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ready", "db": "ok"}
    except Exception as exc:  # noqa: BLE001 — se reporta el motivo
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "db": "error", "detail": str(exc)},
        )
