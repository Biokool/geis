"""Conector Overpass/OSM: vialidades principales cercanas (§ Movimiento).

Consulta ``way[highway = trunk|primary|secondary]`` en un radio (default
2 km) y devuelve nombre (o tipo si la vía no tiene nombre) y la distancia
mínima aproximada del punto a la geometría de la vía (Haversine al
vértice más cercano). Función a nivel módulo, mockeable; ante fallo de
todos los espejos devuelve lista vacía (honesto, no inventa vías).

Los espejos se consultan **en paralelo** (50 s cada uno, 55 s de espera
total): el primario tarda ~30–40 s y kumi/private.coffee suelen agotar el
timeout. ``overpass.osm.ch`` se descarta: responde 200 pero con datos
incompletos (0 vías en el centro de CDMX). Las respuestas se cachean 6 h
por bbox y los fallos 10 min, para no repetir la espera en cada reporte.
"""
from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

log = logging.getLogger(__name__)

OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
OVERPASS_URL = OVERPASS_MIRRORS[0]
TIMEOUT_S = 50.0
#: Espera máxima al primer espejo que responda (se consultan en paralelo).
PRESUPUESTO_TOTAL_S = 55.0
#: Caché en proceso por bbox (los reportes del mismo punto se repiten).
CACHE_TTL_S = 6 * 3600.0
#: Un fallo se recuerda poco: evita repetir 50 s de espera en cada reporte.
CACHE_NEGATIVO_S = 600.0
_CACHE: dict[tuple, tuple[float, list[dict]]] = {}
TIPOS_VIA = ("trunk", "primary", "secondary")


def _consulta(lat: float, lon: float, radio_m: int) -> str:
    """Unión de tres consultas puntuales (más rápida que un regex)."""
    partes = "".join(
        f'way["highway"="{tipo}"](around:{radio_m},{lat},{lon});'
        for tipo in TIPOS_VIA
    )
    return f"[out:json][timeout:25];({partes});out geom;"


def _consultar_espejo(espejo: str, query: str) -> dict:
    resp = httpx.post(
        espejo, data={"data": query}, timeout=TIMEOUT_S,
        headers={"User-Agent": "GEIS/1.0 (geis-local)"},
    )
    resp.raise_for_status()
    return resp.json()


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
    clave = (round(lat, 4), round(lon, 4), int(radio_m), int(limite))
    cacheado = _CACHE.get(clave)
    if cacheado:
        ttl = CACHE_TTL_S if cacheado[1] else CACHE_NEGATIVO_S
        if time.monotonic() - cacheado[0] < ttl:
            return [dict(v) for v in cacheado[1]]
    query = _consulta(lat, lon, radio_m)
    datos = None
    pool = ThreadPoolExecutor(max_workers=len(OVERPASS_MIRRORS))
    futuros = {
        pool.submit(_consultar_espejo, espejo, query): espejo
        for espejo in OVERPASS_MIRRORS
    }
    try:
        for futuro in as_completed(futuros, timeout=PRESUPUESTO_TOTAL_S):
            espejo = futuros[futuro]
            try:
                datos = futuro.result()
                break
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("Overpass %s falló (%s); esperando otro espejo",
                            espejo, type(exc).__name__)
    except TimeoutError:
        log.warning("Overpass sin respuesta en %.0f s", PRESUPUESTO_TOTAL_S)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if not isinstance(datos, dict):
        _CACHE[clave] = (time.monotonic(), [])
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
        clave_via = (v["nombre"], v["tipo"])
        if clave_via not in mejores or v["distancia_m"] < mejores[clave_via]["distancia_m"]:
            mejores[clave_via] = v
    resultado = sorted(mejores.values(), key=lambda v: v["distancia_m"])[:limite]
    _CACHE[clave] = (time.monotonic(), [dict(v) for v in resultado])
    return resultado
