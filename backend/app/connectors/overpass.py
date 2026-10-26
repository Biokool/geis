"""Conector Overpass/OSM: vialidades principales cercanas (§ Movimiento).

Consulta ``way[highway ∈ {trunk, primary, secondary}]`` en un radio
(default 2 km) y devuelve nombre (o tipo si la vía no tiene nombre) y la
distancia mínima aproximada del punto a la geometría de la vía
(Haversine al vértice más cercano). Función a nivel módulo, mockeable;
ante fallo/timeout (15 s) devuelve lista vacía (honesto, no inventa vías).
"""
from __future__ import annotations

import math

import httpx

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
TIMEOUT_S = 15.0
TIPOS_VIA = ("trunk", "primary", "secondary")


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_vialidades(lat: float, lon: float, radio_m: int = 2000,
                     limite: int = 12) -> list[dict]:
    """Vialidades principales a ≤ radio_m: [{nombre, tipo, distancia_m}]."""
    query = (
        "[out:json][timeout:12];"
        f'way["highway"~"^({"|".join(TIPOS_VIA)})$"]'
        f"(around:{radio_m},{lat},{lon});"
        "out geom;"
    )
    try:
        resp = httpx.post(
            OVERPASS_URL, data={"data": query}, timeout=TIMEOUT_S,
            headers={"User-Agent": "GEIS/1.0 (geis-local)"},
        )
        resp.raise_for_status()
        datos = resp.json()
    except (httpx.HTTPError, ValueError):
        return []
    vialidades: list[dict] = []
    for el in (datos.get("elements") if isinstance(datos, dict) else []) or []:
        tags = el.get("tags") or {}
        tipo = tags.get("highway")
        if tipo not in TIPOS_VIA:
            continue
        geometria = el.get("geometry") or []
        if not geometria:
            continue
        dist = min(
            _haversine_m(lat, lon, g["lat"], g["lon"]) for g in geometria
        )
        vialidades.append({
            "nombre": tags.get("name") or tipo,
            "tipo": tipo,
            "distancia_m": round(dist, 1),
        })
    # Únicas por nombre+tipo (una vía larga llega en varios ways): se
    # conserva la distancia mínima.
    mejores: dict[tuple[str, str], dict] = {}
    for v in vialidades:
        clave = (v["nombre"], v["tipo"])
        if clave not in mejores or v["distancia_m"] < mejores[clave]["distancia_m"]:
            mejores[clave] = v
    return sorted(mejores.values(), key=lambda v: v["distancia_m"])[:limite]
