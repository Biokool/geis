"""Tests de la corrección profunda (sin red ni Postgres real).

Cubren los tres endpoints nuevos:
- ``GET /api/v1/leads/count`` (conteo real de ``prod.leads``),
- ``POST /api/v1/analysis/compare`` (comparación de 2 a 5 investigaciones),
- ``DELETE /api/v1/investigations/{id}`` (borrado físico, 204/404).

Se usa ``TestClient`` con ``dependency_overrides[get_db]`` apuntando a
sesiones fake (objetos Python con los métodos que cada endpoint usa) y
``monkeypatch`` sobre ``compute_location_analysis`` en el módulo del
router de análisis.
"""
import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import analysis as analysis_mod
from app.api.v1 import investigations as investigations_mod
from app.api.v1 import leads as leads_mod
from app.db.session import get_db


def _crear_cliente(sesion_fake) -> TestClient:
    """App mínima con los tres routers y la BD reemplazada por la fake."""
    app = FastAPI()
    app.include_router(leads_mod.router, prefix="/api/v1")
    app.include_router(analysis_mod.router, prefix="/api/v1")
    app.include_router(investigations_mod.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: sesion_fake
    return TestClient(app)


# ------------------------------------------------------- fakes: conteo
class _ResultadoConteo:
    """Resultado fake cuyo ``scalar()`` devuelve el total prefijado."""

    def __init__(self, total):
        self._total = total

    def scalar(self):
        return self._total


class SesionConteoFake:
    """Sesión fake para /leads/count: captura (sql, params) de cada execute."""

    def __init__(self, total=0):
        self._total = total
        self.llamadas: list[tuple[str, dict | None]] = []

    def execute(self, stmt, params=None):
        self.llamadas.append((str(stmt), params))
        return _ResultadoConteo(self._total)


# ------------------------------------------------------- fakes: compare
_ANALISIS_FIJO = {
    "anillos": [
        {"radio_m": 1000, "competencia": 3, "demanda_pob_30_59": 1000.0,
         "ism": 333.3},
        {"radio_m": 2000, "competencia": 7, "demanda_pob_30_59": 2500.0,
         "ism": 357.1},
    ],
    "tam_mxn": 123456.0,
    "huff": {"cuota_punto": 0.42},
    "veredicto": "AVANZAR",
}


class SesionInvestigacionesFake:
    """Sesión fake con ``get`` por dict; ``execute`` falla (sin BD real).

    El fallo de ``execute`` es seguro: ``lineage()`` lo captura y devuelve
    ediciones vacías.
    """

    def __init__(self, investigaciones: dict | None = None):
        self._investigaciones = investigaciones or {}
        self.borradas: list = []
        self.commits = 0

    def get(self, _modelo, id_):
        return self._investigaciones.get(id_)

    def execute(self, *args, **kwargs):
        raise RuntimeError("sin BD real en tests")

    def delete(self, obj):
        self.borradas.append(obj)

    def commit(self):
        self.commits += 1


def _investigacion(id_, **extras):
    """Investigación fake con los atributos que usan compare y delete."""
    datos = {
        "investigation_id": id_,
        "title": "Investigación de prueba",
        "territory_kind": "point_buffers",
        "center_lat": 19.419,
        "center_lon": -99.161,
        "radii_m": [1000, 2000],
        "params": {"giro": "cafetería", "scian": "722515"},
    }
    datos.update(extras)
    return SimpleNamespace(**datos)


def _instalar_analisis_fijo(monkeypatch) -> list[dict]:
    """Monkeypatch de compute_location_analysis: dict fijo + captura."""
    llamadas: list[dict] = []

    def fake(db, giro=None, scian=None, lat=None, lon=None, radios=None):
        llamadas.append(
            {"giro": giro, "scian": scian, "lat": lat, "lon": lon,
             "radios": radios}
        )
        return _ANALISIS_FIJO

    monkeypatch.setattr(analysis_mod, "compute_location_analysis", fake)
    return llamadas


# ------------------------------------------------------------ count
def test_count_devuelve_total_del_stub():
    sesion = SesionConteoFake(total=42)
    cliente = _crear_cliente(sesion)
    res = cliente.get("/api/v1/leads/count")
    assert res.status_code == 200
    assert res.json() == {"total": 42}
    sql, params = sesion.llamadas[0]
    assert "COUNT(*)" in sql
    assert "FROM prod.leads" in sql
    assert params == {}


def test_count_filtros_se_traducen_en_query_y_params():
    sesion = SesionConteoFake(total=3)
    cliente = _crear_cliente(sesion)
    res = cliente.get(
        "/api/v1/leads/count",
        params={"etapa": "nuevo", "linea": "koolkat", "source": "denue"},
    )
    assert res.status_code == 200
    assert res.json() == {"total": 3}
    sql, params = sesion.llamadas[0]
    assert "etapa = :etapa" in sql
    assert "linea_recomendada = :linea" in sql
    assert "source = :source" in sql
    assert params == {"etapa": "nuevo", "linea": "koolkat", "source": "denue"}


# ------------------------------------------------------------ compare
def test_compare_422_con_un_solo_id(monkeypatch):
    _instalar_analisis_fijo(monkeypatch)
    cliente = _crear_cliente(SesionInvestigacionesFake())
    res = cliente.post(
        "/api/v1/analysis/compare",
        json={"investigation_ids": [str(uuid.uuid4())]},
    )
    assert res.status_code == 422


def test_compare_422_con_seis_ids(monkeypatch):
    _instalar_analisis_fijo(monkeypatch)
    cliente = _crear_cliente(SesionInvestigacionesFake())
    ids = [str(uuid.uuid4()) for _ in range(6)]
    res = cliente.post(
        "/api/v1/analysis/compare", json={"investigation_ids": ids}
    )
    assert res.status_code == 422


def test_compare_404_con_id_inexistente(monkeypatch):
    _instalar_analisis_fijo(monkeypatch)
    id_ok = uuid.uuid4()
    id_faltante = uuid.uuid4()
    sesion = SesionInvestigacionesFake({id_ok: _investigacion(id_ok)})
    cliente = _crear_cliente(sesion)
    res = cliente.post(
        "/api/v1/analysis/compare",
        json={"investigation_ids": [str(id_ok), str(id_faltante)]},
    )
    assert res.status_code == 404
    assert str(id_faltante) in res.json()["detail"]


def test_compare_422_si_una_investigacion_no_tiene_centro(monkeypatch):
    _instalar_analisis_fijo(monkeypatch)
    id_ok = uuid.uuid4()
    id_sin_centro = uuid.uuid4()
    sesion = SesionInvestigacionesFake({
        id_ok: _investigacion(id_ok),
        id_sin_centro: _investigacion(
            id_sin_centro, title="Sin centro", center_lat=None,
            center_lon=None,
        ),
    })
    cliente = _crear_cliente(sesion)
    res = cliente.post(
        "/api/v1/analysis/compare",
        json={"investigation_ids": [str(id_ok), str(id_sin_centro)]},
    )
    assert res.status_code == 422
    assert str(id_sin_centro) in res.json()["detail"]


def test_compare_200_con_dos_ids_y_forma_completa(monkeypatch):
    llamadas = _instalar_analisis_fijo(monkeypatch)
    id_1 = uuid.uuid4()
    id_2 = uuid.uuid4()
    sesion = SesionInvestigacionesFake({
        id_1: _investigacion(id_1, title="Zona Norte"),
        id_2: _investigacion(
            id_2, title="Zona Sur", territory_kind="municipality",
            params={}, radii_m=None,
        ),
    })
    cliente = _crear_cliente(sesion)
    res = cliente.post(
        "/api/v1/analysis/compare",
        json={"investigation_ids": [str(id_1), str(id_2)]},
    )
    assert res.status_code == 200
    cuerpo = res.json()
    assert "lineage" in cuerpo
    assert len(cuerpo["items"]) == 2

    item = cuerpo["items"][0]
    assert item["id"] == str(id_1)
    assert item["nombre"] == "Zona Norte"
    assert item["territorio"] == "point_buffers"
    assert item["center_lat"] == 19.419
    assert item["center_lon"] == -99.161
    assert item["veredicto"] == "AVANZAR"
    # Del anillo de mayor radio (el último), no del primero.
    assert item["ism"] == 357.1
    assert item["competencia"] == 7
    assert item["poblacion"] == 2500.0
    assert item["tam"] == 123456.0
    assert item["huff_score"] == 0.42

    # El motor recibió giro/scian de params y los radios guardados…
    assert llamadas[0]["giro"] == "cafetería"
    assert llamadas[0]["scian"] == "722515"
    assert llamadas[0]["radios"] == [1000, 2000]
    # …y sin radii_m guardados usó el default [1000, 2000].
    assert llamadas[1]["giro"] is None
    assert llamadas[1]["scian"] is None
    assert llamadas[1]["radios"] == [1000, 2000]


# ------------------------------------------------------------ delete
def test_delete_204_cuando_existe():
    id_ = uuid.uuid4()
    inv = _investigacion(id_)
    sesion = SesionInvestigacionesFake({id_: inv})
    cliente = _crear_cliente(sesion)
    res = cliente.delete(f"/api/v1/investigations/{id_}")
    assert res.status_code == 204
    assert res.content == b""
    assert sesion.borradas == [inv]
    assert sesion.commits == 1


def test_delete_404_cuando_no_existe():
    id_ = uuid.uuid4()
    sesion = SesionInvestigacionesFake()
    cliente = _crear_cliente(sesion)
    res = cliente.delete(f"/api/v1/investigations/{id_}")
    assert res.status_code == 404
    assert sesion.borradas == []
    assert sesion.commits == 0
