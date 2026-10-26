"""Geocoding real con OpenStreetMap/Nominatim + parser de links de Maps.

Funciones a nivel módulo (mockeables en tests sin red):

- :func:`parse_maps_link` — extrae (lat, lon) de un link de Google Maps:
  ``@lat,lon``, ``!3d{lat}!4d{lon}``, ``?q=lat,lon``, ``query=lat,lon`` y
  ``/place/.../@lat,lon`` (cubierto por la regla ``@``).
- :func:`resolve_short_link` — sigue el redirect de un link corto
  (``goo.gl`` / ``maps.app.goo.gl``) con httpx y devuelve la URL final.
- :func:`nominatim_search` — dirección en texto → punto (MX, limit=1).
- :func:`nominatim_reverse` — punto → componentes legibles (colonia,
  municipio, entidad, CP) para la etiqueta de ubicación.

Regla de honestidad: si nada resuelve, las funciones devuelven None y el
endpoint responde 422; NUNCA se devuelve un punto por defecto.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
USER_AGENT = "GEIS/1.0 (geis-local)"
TIMEOUT_S = 10.0

_RE_AT = re.compile(r"@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)")
_RE_3D4D = re.compile(r"!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)")
_RE_Q = re.compile(r"[?&](?:q|query|ll)=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)")
_RE_COORDS_SUELTAS = re.compile(r"^(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)$")

DOMINIOS_CORTOS = ("goo.gl", "maps.app.goo.gl")
#: Dominios a los que se permite seguir redirects (anti-SSRF).
HOSTS_PERMITIDOS = {"goo.gl", "www.goo.gl", "maps.app.goo.gl",
                    "google.com", "www.google.com", "maps.google.com"}


def _valido(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180


def parse_maps_link(texto: str | None) -> tuple[float, float] | None:
    """Extrae (lat, lon) de una URL/texto de Maps, o None si no trae punto."""
    if not texto:
        return None
    t = texto.strip()
    for patron, orden in ((_RE_3D4D, (0, 1)), (_RE_AT, (0, 1)), (_RE_Q, (0, 1))):
        m = patron.search(t)
        if m:
            lat, lon = float(m.group(1 + orden[0])), float(m.group(2))
            # !3d es latitud y !4d longitud; @ y q también son lat,lon.
            if _valido(lat, lon):
                return (lat, lon)
    m = _RE_COORDS_SUELTAS.match(t)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if _valido(lat, lon):
            return (lat, lon)
    return None


def es_link_corto(texto: str | None) -> bool:
    if not texto:
        return False
    host = (urlparse(texto.strip()).hostname or "").lower()
    return host in DOMINIOS_CORTOS


def es_url(texto: str | None) -> bool:
    return bool(texto) and texto.strip().lower().startswith(("http://", "https://"))


def _url_permitida(url: str) -> bool:
    """Solo http(s) a dominios de Google Maps/goo.gl (anti-SSRF)."""
    partes = urlparse(url)
    if partes.scheme not in ("http", "https"):
        return False
    return (partes.hostname or "").lower() in HOSTS_PERMITIDOS


def resolve_short_link(url: str) -> str | None:
    """Sigue el redirect de un link corto y devuelve la URL final (o None).

    Anti-SSRF: solo se aceptan URLs http(s) en dominios de Google/goo.gl y
    cada salto del redirect se valida con la misma allowlist (sin seguir
    redirects automáticamente hacia hosts internos).
    """
    actual = (url or "").strip()
    if not _url_permitida(actual):
        return None
    try:
        for _ in range(4):
            resp = httpx.get(
                actual, follow_redirects=False, timeout=TIMEOUT_S,
                headers={"User-Agent": USER_AGENT},
            )
            destino = resp.headers.get("location")
            if resp.is_redirect and destino:
                actual = urljoin(actual, destino)
                if not _url_permitida(actual):
                    return None
                continue
            return str(resp.url) if _url_permitida(str(resp.url)) else None
    except httpx.HTTPError:
        return None
    return None


def nominatim_search(direccion: str) -> dict | None:
    """Geocodifica una dirección en texto con Nominatim (solo México).

    Devuelve el primer resultado crudo de la API o None si no resuelve.
    """
    try:
        resp = httpx.get(
            f"{NOMINATIM_BASE}/search",
            params={
                "q": direccion, "format": "jsonv2", "limit": 1,
                "addressdetails": 1, "countrycodes": "mx",
            },
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        datos = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    if isinstance(datos, list) and datos:
        return datos[0]
    return None


def nominatim_reverse(lat: float, lon: float) -> dict | None:
    """Geocodificación inversa: componentes legibles del punto (o None)."""
    try:
        resp = httpx.get(
            f"{NOMINATIM_BASE}/reverse",
            params={"lat": lat, "lon": lon, "format": "jsonv2",
                    "addressdetails": 1},
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        datos = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def componentes_de(address: dict | None) -> dict:
    """Normaliza el ``address`` de Nominatim a componentes GEIS."""
    a = address or {}
    return {
        "colonia": a.get("suburb") or a.get("neighbourhood") or a.get("quarter"),
        "municipio": (
            a.get("city") or a.get("town") or a.get("municipality")
            or a.get("county") or a.get("village")
        ),
        "entidad": a.get("state"),
        "cp": a.get("postcode"),
    }


def etiqueta_legible(componentes: dict, lat: float, lon: float) -> str:
    """«Colonia, Municipio, Entidad» si hay componentes; si no, el punto."""
    partes = [
        componentes.get("colonia"), componentes.get("municipio"),
        componentes.get("entidad"),
    ]
    legible = ", ".join(p for p in partes if p)
    return legible or f"Punto {lat:.5f}, {lon:.5f}"
