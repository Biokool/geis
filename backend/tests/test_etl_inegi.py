"""Tests unitarios de la ingesta INEGI, catálogo SCIAN y conectores (sin red ni BD)."""
from __future__ import annotations

from datetime import date

import pytest

from app.connectors import overpass
from app.connectors.denue_api import DenueApiClient
from app.data.catalogo_scian import ALIASES, OVERRIDES, SECTOR_PARAMS
from app.etl.jobs.censo_ageb import _nse, _pct
from app.etl.jobs.denue_bulk import _coord, _estrato_ordinal, _fecha, _scian


@pytest.fixture(autouse=True)
def _cache_overpass_limpia():
    overpass._CACHE.clear()
    yield
    overpass._CACHE.clear()


def test_estrato_ordinal_mapea_los_siete_rangos():
    assert _estrato_ordinal("0 a 5 personas") == 1
    assert _estrato_ordinal("6 a 10 personas") == 2
    assert _estrato_ordinal("11 a 30 personas") == 3
    assert _estrato_ordinal("31 a 50 personas") == 4
    assert _estrato_ordinal("51 a 100 personas") == 5
    assert _estrato_ordinal("101 a 250 personas") == 6
    assert _estrato_ordinal("251 y más personas") == 7
    assert _estrato_ordinal(None) == 1
    assert _estrato_ordinal("sin dato") == 1


def test_fecha_scian_y_coordenadas_toleran_formatos_inegi():
    assert _fecha("2020-05-01") == date(2020, 5, 1)
    assert _fecha("01/05/2020") == date(2020, 5, 1)
    assert _fecha("20200501") == date(2020, 5, 1)
    assert _fecha("") is None
    assert _fecha("no es fecha") is None
    assert _scian("722515") == "722515"
    assert _scian(722515) == "722515"
    assert _scian("72") == "000072"
    assert _scian("") is None
    assert _coord("-100.39") == -100.39
    assert _coord("20,59") == 20.59
    assert _coord("x") is None


def test_pct_y_nse_respetan_limites_y_bandas():
    assert _pct(3, 4) == 75.0
    assert _pct(None, 10) is None
    assert _pct(5, 0) is None
    assert _pct(11, 10) == 100.0
    assert _pct(-1, 10) == 0.0

    todo = {"internet": 100.0, "computadora": 100.0, "automovil": 100.0, "celular": 100.0}
    assert _nse(todo) == (1.0, "Alto")
    assert _nse({k: 70.0 for k in todo}) == (0.7, "Medio a medio alto")
    assert _nse({k: 50.0 for k in todo}) == (0.5, "Medio")
    assert _nse({k: 35.0 for k in todo}) == (0.35, "Medio bajo")
    assert _nse({k: 10.0 for k in todo}) == (0.1, "Bajo")
    assert _nse({"internet": None, "computadora": None,
                 "automovil": None, "celular": None}) == (None, None)
    score, banda = _nse({"internet": 90.0, "computadora": None,
                         "automovil": None, "celular": None})
    assert score == 0.9 and banda == "Alto"


def test_catalogo_scian_invariantes():
    for sector, (thermal, attr, lam) in SECTOR_PARAMS.items():
        assert len(sector) == 2 and sector.isdigit()
        assert 0 <= thermal <= 1 and 0 <= attr <= 1 and lam > 0
    for codigo, (thermal, attr, lam) in OVERRIDES.items():
        assert len(codigo) == 6 and codigo.isdigit()
        assert codigo[:2] in SECTOR_PARAMS
        assert 0 <= thermal <= 1 and 0 <= attr <= 1 and lam > 0
    for codigo, etiquetas in ALIASES.items():
        assert len(codigo) == 6 and codigo.isdigit()
        codigo_en_sector = codigo in OVERRIDES or codigo[:2] in SECTOR_PARAMS
        assert codigo_en_sector, codigo
        assert etiquetas, codigo
        assert len({e for e, _ in etiquetas}) == len(etiquetas), codigo
        for etiqueta, confianza in etiquetas:
            assert etiqueta.strip() and etiqueta == etiqueta.lower()
            assert 0 < confianza <= 1


def test_denue_stub_tiene_forma_del_api_real():
    cliente = DenueApiClient(token="TOKEN")
    cliente.stub = True
    resultados = cliente.buscar(20.59, -100.39, 500, "722515")
    assert resultados
    claves = {"CLEE", "Id", "Nombre", "Clase_actividad", "Estrato",
              "Latitud", "Longitud", "stub"}
    assert claves <= set(resultados[0])
    assert cliente.ficha("123") is None


def test_denue_endpoints_reales_llevan_token_en_ruta():
    cliente = DenueApiClient(token="TOKEN")
    llamadas: list[str] = []
    cliente._get = lambda path, params=None: llamadas.append(path) or []  # type: ignore[method-assign]
    cliente.buscar(20.5, -100.3, 9999, "722515")
    assert llamadas[-1] == "buscar/722515/20.5,-100.3/5000/TOKEN"
    cliente.buscar(20.5, -100.3, 400)
    assert llamadas[-1] == "buscar/todos/20.5,-100.3/400/TOKEN"
    cliente.ficha("6380939")
    assert llamadas[-1] == "ficha/6380939/TOKEN"


def test_overpass_usa_el_siguiente_espejo_si_falla_el_primero(monkeypatch):
    llamadas: list[str] = []

    class Respuesta:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"elements": [{
                "tags": {"highway": "primary", "name": "Avenida de Prueba"},
                "geometry": [{"lat": 20.5, "lon": -100.4}],
            }]}

    def post_falso(url, data=None, timeout=None, headers=None):
        llamadas.append(url)
        if len(llamadas) == 1:
            raise overpass.httpx.HTTPError("espejo caído")
        return Respuesta()

    monkeypatch.setattr(overpass.httpx, "post", post_falso)
    vias = overpass.fetch_vialidades(20.5, -100.4)
    assert set(llamadas) == set(overpass.OVERPASS_MIRRORS)
    assert vias == [{"nombre": "Avenida de Prueba", "tipo": "primary", "distancia_m": 0.0}]


def test_overpass_devuelve_vacio_si_todos_los_espejos_fallan(monkeypatch):
    llamadas: list[str] = []

    def post_falso(url, data=None, timeout=None, headers=None):
        llamadas.append(url)
        raise overpass.httpx.HTTPError("caído")

    monkeypatch.setattr(overpass.httpx, "post", post_falso)
    assert overpass.fetch_vialidades(20.5, -100.4) == []
    # El fallo se recuerda: la segunda llamada no vuelve a esperar a Overpass.
    assert overpass.fetch_vialidades(20.5, -100.4) == []
    assert len(llamadas) == len(overpass.OVERPASS_MIRRORS)


def test_overpass_cachea_la_misma_consulta(monkeypatch):
    llamadas: list[str] = []

    class Respuesta:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"elements": [{
                "tags": {"highway": "primary", "name": "Av. Cache"},
                "geometry": [{"lat": 20.6, "lon": -100.3}],
            }]}

    def post_falso(url, data=None, timeout=None, headers=None):
        llamadas.append(url)
        return Respuesta()

    monkeypatch.setattr(overpass.httpx, "post", post_falso)
    primera = overpass.fetch_vialidades(20.6, -100.3)
    llamadas_primera = len(llamadas)
    segunda = overpass.fetch_vialidades(20.6, -100.3)
    assert primera == segunda
    assert len(llamadas) == llamadas_primera
