"""Conector de isócronas Valhalla (OSM) — alcance por tiempo (§3.7).

``POST {VALHALLA_BASE_URL}/isochrone`` con ``polygons: true``:

- peatón 5 min (costing ``pedestrian``),
- moto 10 min (costing ``motorcycle``; si el servicio lo rechaza se
  reintenta con ``bicycle`` y se etiqueta el modo real usado),
- auto 15 min (costing ``auto``).

Fallback honesto: ante fallo/timeout (10 s) devuelve lista vacía y el
contexto del reporte marca el alcance como radios (no se inventan
polígonos). La función es a nivel módulo para poder mockearla sin red.
"""
from __future__ import annotations

import os

import httpx

TIMEOUT_S = 10.0

#: (modo GEIS, minutos, costing Valhalla, costing de respaldo o None)
MODOS: list[tuple[str, int, str, str | None]] = [
    ("peaton", 5, "pedestrian", None),
    ("moto", 10, "motorcycle", "bicycle"),
    ("auto", 15, "auto", None),
]


def base_url() -> str:
    return os.getenv("VALHALLA_BASE_URL", "https://valhalla1.openstreetmap.de").rstrip("/")


def _pedir_isocrona(lat: float, lon: float, minutos: int, costing: str) -> dict | None:
    """Un polígono de isócrona (Feature GeoJSON) o None si el servicio falla."""
    try:
        resp = httpx.post(
            f"{base_url()}/isochrone",
            json={
                "locations": [{"lat": lat, "lon": lon}],
                "costing": costing,
                "contours": [{"time": minutos}],
                "polygons": True,
            },
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        datos = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    features = datos.get("features") if isinstance(datos, dict) else None
    if not features:
        return None
    return features[0]


def fetch_isochrones(lat: float, lon: float) -> list[dict]:
    """Isócronas 5/10/15 min por modo. Lista vacía si Valhalla no responde."""
    isocronas: list[dict] = []
    for modo, minutos, costing, respaldo in MODOS:
        feature = _pedir_isocrona(lat, lon, minutos, costing)
        costing_real = costing
        if feature is None and respaldo:
            feature = _pedir_isocrona(lat, lon, minutos, respaldo)
            costing_real = respaldo
        if feature is None:
            continue
        props = feature.get("properties") or {}
        isocronas.append({
            "modo": modo,
            "modo_real": costing_real,
            "costing": costing_real,
            "minutos": minutos,
            "alcance": "isocrona",
            "geometria": feature.get("geometry"),
            "contorno": props.get("contour"),
        })
    return isocronas
