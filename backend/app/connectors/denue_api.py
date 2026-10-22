"""Cliente del API del DENUE (INEGI) con caché, reintentos y modo stub.

- Sin ``DENUE_API_TOKEN`` opera en **modo stub**: devuelve datos de muestra
  deterministas sin fallar (útil para desarrollo y tests).
- Con token: consulta el API real con caché en memoria (dict + TTL) y
  backoff exponencial ante 429/5xx.
"""
from __future__ import annotations

import hashlib
import logging
import random
import time
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)

#: TTL de la caché en memoria (segundos).
CACHE_TTL_S = 3600


@dataclass
class _CacheEntry:
    value: object
    expires_at: float


class DenueApiClient:
    """Cliente del API DENUE v1 del INEGI."""

    def __init__(
        self,
        token: str = "",
        base_url: str = "",
        timeout_s: float = 20.0,
        cache_ttl_s: float = CACHE_TTL_S,
    ) -> None:
        self.token = token or settings.denue_api_token
        self.base_url = (base_url or settings.denue_api_base_url).rstrip("/")
        self.timeout_s = timeout_s or settings.denue_api_timeout_s
        self.cache_ttl_s = cache_ttl_s
        self._cache: dict[str, _CacheEntry] = {}
        self.stub = not bool(self.token)
        if self.stub:
            log.info("DENUE_API_TOKEN ausente: conector en modo stub (datos de muestra)")

    # ------------------------------------------------------------------ caché
    def _cache_get(self, key: str) -> object | None:
        entry = self._cache.get(key)
        if entry and entry.expires_at > time.time():
            return entry.value
        self._cache.pop(key, None)
        return None

    def _cache_set(self, key: str, value: object) -> None:
        self._cache[key] = _CacheEntry(value, time.time() + self.cache_ttl_s)

    # --------------------------------------------------------------- reintentos
    def _get(self, path: str, params: dict) -> list[dict]:
        """GET con backoff exponencial ante 429/5xx (máx. 4 intentos)."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_exc: Exception | None = None
        for intento in range(4):
            try:
                resp = httpx.get(url, params=params, timeout=self.timeout_s)
                if resp.status_code in (429, 500, 502, 503, 504):
                    espera = 2**intento
                    log.warning(
                        "DENUE %s → %s; reintento en %ss (intento %d/4)",
                        url, resp.status_code, espera, intento + 1,
                    )
                    time.sleep(espera)
                    continue
                resp.raise_for_status()
                datos = resp.json()
                return datos if isinstance(datos, list) else [datos]
            except httpx.HTTPError as exc:  # error de red/timeout: también reintenta
                last_exc = exc
                espera = 2**intento
                log.warning("DENUE error de red (%s); reintento en %ss", exc, espera)
                time.sleep(espera)
        raise RuntimeError(f"DENUE API no disponible tras 4 intentos: {last_exc}")

    # ------------------------------------------------------------------ API
    def buscar(
        self,
        lat: float,
        lon: float,
        radio_m: int = 1000,
        scian: str | None = None,
    ) -> list[dict]:
        """Busca establecimientos cerca de un punto.

        En modo stub devuelve datos de muestra deterministas (seed por
        coordenadas), con la misma forma que el API real.
        """
        if self.stub:
            return self._stub(lat, lon, radio_m, scian)

        clave = f"buscar:{lat:.5f}:{lon:.5f}:{radio_m}:{scian}"
        cached = self._cache_get(clave)
        if cached is not None:
            return cached  # type: ignore[return-value]

        params = {
            "lat": lat, "lon": lon, "radio": radio_m, "token": self.token,
        }
        if scian:
            params["scian"] = scian
        datos = self._get("buscar", params)
        self._cache_set(clave, datos)
        return datos

    def ficha(self, denue_id: str) -> dict | None:
        """Ficha de un establecimiento por su Id DENUE."""
        if self.stub:
            return None
        clave = f"ficha:{denue_id}"
        cached = self._cache_get(clave)
        if cached is not None:
            return cached  # type: ignore[return-value]
        datos = self._get("ficha", {"id": denue_id, "token": self.token})
        ficha = datos[0] if datos else None
        self._cache_set(clave, ficha)
        return ficha

    # ------------------------------------------------------------------ stub
    @staticmethod
    def _stub(lat: float, lon: float, radio_m: int, scian: str | None) -> list[dict]:
        """Datos de muestra deterministas: mismo input → mismo output."""
        semilla = int(hashlib.md5(f"{lat:.4f}|{lon:.4f}|{radio_m}|{scian}".encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(semilla)
        giros = [
            ("722515", "Cafeterías", ["Café Roma", "Café Toscano", "La Esquina del Café"]),
            ("311830", "Tortillerías", ["Tortillería La Guadalupana", "Tortillas Doña Mary"]),
            ("811111", "Talleres mecánicos", ["Taller Hernández", "Auto Servicio Condesa"]),
        ]
        if scian:
            giros = [g for g in giros if g[0] == scian] or giros
        n = rng.randint(3, 8)
        resultados = []
        for i in range(n):
            codigo, desc, nombres = rng.choice(giros)
            resultados.append({
                "Id": f"STUB-{semilla % 100000:05d}-{i:02d}",
                "Nombre": rng.choice(nombres),
                "ClaseSCIAN": codigo,
                "DescripcionSCIAN": desc,
                "Estrato": rng.choice(["0 a 5", "6 a 10", "11 a 30"]),
                "Latitud": round(lat + rng.uniform(-0.008, 0.008), 6),
                "Longitud": round(lon + rng.uniform(-0.008, 0.008), 6),
                "stub": True,
            })
        return resultados

    def limpiar_cache(self) -> None:
        self._cache.clear()


#: Instancia compartida (inyectable en tests).
denue_client = DenueApiClient()


@dataclass
class StubState:
    """Estado auxiliar para documentar el modo stub en respuestas."""

    activo: bool = field(default_factory=lambda: denue_client.stub)
