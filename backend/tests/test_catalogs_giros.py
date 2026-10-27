"""Tests del catálogo de giros expuesto a la UI (ADR-013).

Sin Postgres: la sesión fake responde a la consulta del endpoint
(``cat_giro_scian ⋈ cat_scian``) y deja que el linaje caiga en el
capturador de ``edition_labels``.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import catalogs as catalogs_mod
from app.db.session import get_db


class ResultadoFake:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class SesionGirosFake:
    def __init__(self):
        self.ultimo_sql = ""
        self.ultimos_params: dict = {}

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "FROM prod.cat_giro_scian" in sql:
            self.ultimo_sql = sql
            self.ultimos_params = params or {}
            return ResultadoFake([
                ("gasolinera", "468411",
                 "Comercio al por menor de gasolina y diesel", 1.0),
                ("abarrotes", "461110",
                 "Comercio al por menor en tiendas de abarrotes", 0.95),
            ])
        raise RuntimeError("sin BD real en tests")

    def rollback(self):
        pass


def _cliente(sesion: SesionGirosFake) -> TestClient:
    app = FastAPI()
    app.include_router(catalogs_mod.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: sesion
    return TestClient(app)


def test_catalogs_giros_expone_alias_y_clase_scian():
    sesion = SesionGirosFake()
    res = _cliente(sesion).get("/api/v1/catalogs/giros")
    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["total"] == 2
    assert cuerpo["lineage"]["editions"] == []
    gas = next(i for i in cuerpo["items"] if i["giro"] == "gasolinera")
    assert gas["scian_code"] == "468411"
    assert "gasolina" in gas["description"]
    assert gas["confidence"] == 1.0


def test_catalogs_giros_filtra_y_acota_resultados():
    sesion = SesionGirosFake()
    res = _cliente(sesion).get(
        "/api/v1/catalogs/giros", params={"q": "gas", "limit": 25},
    )
    assert res.status_code == 200
    assert "g.giro_label ILIKE" in sesion.ultimo_sql
    assert sesion.ultimos_params["q"] == "%gas%"
    assert sesion.ultimos_params["lim"] == 25


def test_catalogs_giros_valida_limit():
    res = _cliente(SesionGirosFake()).get(
        "/api/v1/catalogs/giros", params={"limit": 5000},
    )
    assert res.status_code == 422
