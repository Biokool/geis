"""Proxy de clima Open-Meteo con caché en memoria (TTL 6h).

Regla de negocio v1: la temperatura de zona alimenta el componente
térmico del score unificado (>30 °C ⇒ x_temp = 1).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.schemas.radar import WeatherOut

router = APIRouter(prefix="/geo", tags=["geo"])

#: Caché en memoria: (lat, lon) → (temperature_c, fetched_at, expira_en).
_CACHE: dict[tuple[float, float], tuple[float | None, float, float]] = {}

#: TTL de 6 horas, como en el dashboard Radar original.
TTL_S = 6 * 3600

_OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


def _clima_actual(lat: float, lon: float) -> tuple[float | None, bool]:
    """Temperatura actual (°C); devuelve (valor, desde_cache)."""
    clave = (round(lat, 3), round(lon, 3))
    ahora = time.time()
    hit = _CACHE.get(clave)
    if hit is not None and hit[2] > ahora:
        return hit[0], True
    try:
        resp = httpx.get(
            _OPEN_METEO,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        temp = resp.json().get("current", {}).get("temperature_2m")
        temp = float(temp) if temp is not None else None
    except Exception as exc:  # noqa: BLE001 — se reporta el motivo
        raise HTTPException(
            status_code=502,
            detail=f"Open-Meteo no disponible: {exc}",
        ) from exc
    _CACHE[clave] = (temp, ahora, ahora + TTL_S)
    return temp, False


@router.get("/weather", response_model=WeatherOut)
def clima(
    lat: float = Query(..., description="Latitud"),
    lon: float = Query(..., description="Longitud"),
):
    """Temperatura actual de una coordenada (Open-Meteo, caché 6h)."""
    temp, cached = _clima_actual(lat, lon)
    hit = _CACHE.get((round(lat, 3), round(lon, 3)))
    fetched_at = datetime.fromtimestamp(hit[1], tz=timezone.utc) if hit else datetime.now(
        timezone.utc
    )
    return WeatherOut(
        lat=lat,
        lon=lon,
        temperature_c=temp,
        fetched_at=fetched_at,
        cached=cached,
    )
