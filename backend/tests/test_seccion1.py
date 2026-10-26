"""Tests de la Sección 1 (Ubicaciones/Sabueso) — sin red ni Postgres real.

HTTP SIEMPRE mockeado: Nominatim, resolución de links cortos, Valhalla y
Overpass se sustituyen con ``monkeypatch`` sobre las funciones a nivel
módulo. La BD se sustituye con sesiones fake que responden por marcador
de consulta SQL (patrón de la casa, ver test_correccion_profunda.py).
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analytics.anclas import aplicar_efecto_ancla, detectar_anclas
from app.analytics.categorias import categoria_de, conteo_por_categoria
from app.analytics.huff import p_ij
from app.analytics.movilidad import proxy_peatonal, proxy_vehicular
from app.analytics.sector_data import FICHAS, buscar_ficha
from app.api.v1 import analysis as analysis_mod
from app.api.v1 import investigations as investigations_mod
from app.api.v1 import reports as reports_mod
from app.api.v1 import territories as territories_mod
from app.db.session import get_db
from app.geo.geocoding import es_link_corto, parse_maps_link, resolve_short_link
from app.models.investigations import UserInvestigation  # noqa: F401  (registro)
from app.models.reports import Report, ReportShare
from app.reports import context as context_mod
from app.reports.builder import build_location_report


# ------------------------------------------------------------- utilidades --
class SesionSinBD:
    """Sesión fake cuyo execute siempre falla (lineage lo captura)."""

    def execute(self, *args, **kwargs):
        raise RuntimeError("sin BD real en tests")


class ResultadoFake:
    """Resultado fake con first()/all()/scalar() prefijados."""

    def __init__(self, first_row=None, all_rows=None, scalar_val=None):
        self._first = first_row
        self._all = all_rows or []
        self._scalar = scalar_val

    def first(self):
        return self._first

    def all(self):
        return self._all

    def scalar(self):
        return self._scalar


def _cliente(*modulos, sesion) -> TestClient:
    app = FastAPI()
    for modulo in modulos:
        app.include_router(modulo.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: sesion
    return TestClient(app)


_REVERSE_ROMA = {
    "display_name": "Roma Norte, Cuauhtémoc, Ciudad de México",
    "address": {
        "suburb": "Roma Norte", "city": "Cuauhtémoc",
        "state": "Ciudad de México", "postcode": "06700",
    },
}


# ------------------------------------------------------------ geocoding --
def test_parse_maps_link_formatos():
    assert parse_maps_link(
        "https://www.google.com/maps/@19.4326,-99.1332,17z"
    ) == (19.4326, -99.1332)
    assert parse_maps_link(
        "https://www.google.com/maps/place/X/@19.4,-99.1,17z/data=!3d19.4195!4d-99.1627"
    ) == (19.4195, -99.1627)
    assert parse_maps_link(
        "https://maps.google.com/?q=20.6597,-103.3496"
    ) == (20.6597, -103.3496)
    assert parse_maps_link(
        "https://www.google.com/maps/search/?api=1&query=19.4195,-99.1627"
    ) == (19.4195, -99.1627)
    assert parse_maps_link("una dirección sin coordenadas") is None


def test_geocode_link_maps_punto_exacto(monkeypatch):
    monkeypatch.setattr(territories_mod, "nominatim_reverse",
                        lambda lat, lon: _REVERSE_ROMA)
    cliente = _cliente(territories_mod, sesion=SesionSinBD())
    res = cliente.post("/api/v1/territories/geocode", json={
        "address": "https://www.google.com/maps/@19.4326,-99.1332,17z",
    })
    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["lat"] == 19.4326 and cuerpo["lon"] == -99.1332
    assert cuerpo["stub"] is False
    assert cuerpo["fuente"] == "link_maps"
    assert cuerpo["colonia"] == "Roma Norte"


def test_geocode_link_3d4d(monkeypatch):
    monkeypatch.setattr(territories_mod, "nominatim_reverse",
                        lambda lat, lon: _REVERSE_ROMA)
    cliente = _cliente(territories_mod, sesion=SesionSinBD())
    res = cliente.post("/api/v1/territories/geocode", json={
        "address": "https://www.google.com/maps/place/Café/@19.4,-99.1,17z/"
                   "data=!4m6!3d19.4195!4d-99.1627",
    })
    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["lat"] == 19.4195 and cuerpo["lon"] == -99.1627
    assert cuerpo["fuente"] == "link_maps"


def test_geocode_link_corto_con_redirect(monkeypatch):
    monkeypatch.setattr(
        territories_mod, "resolve_short_link",
        lambda url: "https://www.google.com/maps/@20.6597,-103.3496,17z",
    )
    monkeypatch.setattr(territories_mod, "nominatim_reverse",
                        lambda lat, lon: None)
    monkeypatch.setattr(
        territories_mod, "nominatim_search",
        lambda direccion: pytest.fail("no debe geocodificar un link corto"),
    )
    cliente = _cliente(territories_mod, sesion=SesionSinBD())
    res = cliente.post("/api/v1/territories/geocode", json={
        "address": "https://maps.app.goo.gl/abc123xyz",
    })
    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["lat"] == 20.6597 and cuerpo["lon"] == -103.3496
    assert cuerpo["fuente"] == "link_maps" and cuerpo["stub"] is False


def test_link_corto_solo_dominios_permitidos():
    # Un texto que solo contiene «goo.gl» en otra parte no es link corto.
    assert es_link_corto("https://maps.app.goo.gl/abc123")
    assert es_link_corto("https://goo.gl/maps/abc")
    assert not es_link_corto("http://169.254.169.254/goo.gl")
    assert not es_link_corto("https://evil.example/?redirect=goo.gl")
    # Ni siquiera se intenta la petición a un host no permitido (anti-SSRF).
    assert resolve_short_link("http://127.0.0.1/goo.gl") is None
    assert resolve_short_link("file:///etc/passwd") is None


def test_geocode_direccion_via_nominatim(monkeypatch):
    monkeypatch.setattr(territories_mod, "nominatim_search", lambda direccion: {
        "lat": "19.4195", "lon": "-99.1627",
        "display_name": "Colima 123, Roma Norte, Cuauhtémoc, CDMX",
        "address": {"suburb": "Roma Norte", "city": "Cuauhtémoc",
                    "state": "Ciudad de México", "postcode": "06700"},
    })
    cliente = _cliente(territories_mod, sesion=SesionSinBD())
    res = cliente.post("/api/v1/territories/geocode", json={
        "address": "Colima 123, Roma Norte, CDMX",
    })
    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["fuente"] == "nominatim" and cuerpo["stub"] is False
    assert cuerpo["lat"] == 19.4195 and cuerpo["lon"] == -99.1627
    assert cuerpo["colonia"] == "Roma Norte"
    assert cuerpo["municipio"] == "Cuauhtémoc"
    assert cuerpo["cp"] == "06700"
    assert "Roma Norte" in cuerpo["label"]


def test_geocode_direccion_irresoluble_422(monkeypatch):
    monkeypatch.setattr(territories_mod, "nominatim_search", lambda d: None)
    cliente = _cliente(territories_mod, sesion=SesionSinBD())
    res = cliente.post("/api/v1/territories/geocode", json={
        "address": "Calle Falsa 123, Narnia",
    })
    assert res.status_code == 422
    # Nunca se devuelve un punto falso (antes: stub del Zócalo).
    assert "19.4326" not in res.text


def test_geocode_coordenadas_directas(monkeypatch):
    monkeypatch.setattr(territories_mod, "nominatim_reverse",
                        lambda lat, lon: _REVERSE_ROMA)
    cliente = _cliente(territories_mod, sesion=SesionSinBD())
    res = cliente.post("/api/v1/territories/geocode", json={
        "lat": 19.4195, "lon": -99.1627,
    })
    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["fuente"] == "coordenadas" and cuerpo["stub"] is False
    assert cuerpo["etiqueta" if "etiqueta" in cuerpo else "label"]


# ------------------------------------------------- categorías y sectorial --
def test_categorias_scian():
    assert categoria_de("722515") == "restaurantes"
    assert categoria_de("464111") == "salud"        # farmacia antes que comercio
    assert categoria_de("622111") == "salud"
    assert categoria_de("461110") == "compras_diarias"
    assert categoria_de("611311") == "educacion"
    assert categoria_de("522110") == "bancos"
    assert categoria_de("713940") == "gimnasios"
    assert categoria_de("812320") == "especializados"  # tintorería
    assert categoria_de("468411") == "plazas_gasolineras"
    assert categoria_de("999999") is None
    conteo = conteo_por_categoria(
        [{"nombre": "Café A", "scian_code": "722515"},
         {"nombre": "OXXO", "scian_code": "462112"}],
        scian_giro="722515",
    )
    assert conteo["total"] == 2
    por_id = {c["categoria"]: c for c in conteo["categorias"]}
    assert len(por_id) == 9
    assert por_id["similares"]["conteo"] == 1
    assert por_id["similares"]["ejemplos"] == ["Café A"]


def test_fichas_sectoriales_15_giros():
    claves = {f["clave"] for f in FICHAS.values()}
    assert len(claves) == 15
    cafe = buscar_ficha("cafetería")
    assert cafe["scian"] == ["722515"]
    assert cafe["tam_supuestos"]["gasto_pc_mxn_anual"] == 2400.0
    assert cafe["delivery"] is True
    assert buscar_ficha("Quiero poner un SUSHI en la Roma")["clave"] == "sushi"
    assert buscar_ficha("laboratorio clínico")["sector"]["hora_pico"] == "7:00–10:00"
    assert buscar_ficha("giro que no existe xyz") is None
    for ficha in FICHAS.values():
        be = ficha["break_even"]
        assert set(be["costos_fijos"]) >= {
            "nomina", "renta", "servicios", "contador",
            "impuestos", "mantenimiento", "imprevistos",
        }
        # Insumos es variable: fuera de los fijos y sin doble conteo.
        assert "insumos" not in be["costos_fijos"]
        assert be["costos_variables"]["insumos"] > 0
        assert be["total_costos_fijos"] == pytest.approx(
            sum(be["costos_fijos"].values())
        )
        assert be["margen_contribucion"] > 0


def test_proxies_movilidad_siempre_estimados():
    vialidades = [
        {"nombre": "Insurgentes", "tipo": "primary", "distancia_m": 120.0},
        {"nombre": "Insurgentes", "tipo": "primary", "distancia_m": 300.0},
        {"nombre": "Obrero Mundial", "tipo": "secondary", "distancia_m": 800.0},
    ]
    veh = proxy_vehicular(vialidades, poblacion_radio=24000)
    assert veh["estimado"] is True
    bajo, alto = veh["rango_vehiculos_dia"]
    assert 0 < bajo < alto  # la vía repetida cuenta una sola vez
    assert 0 <= veh["nivel"] <= 100
    pea = proxy_peatonal(24000, radio_m=2000, pea_ocupada=10800, n_atractores=8)
    assert pea["estimado"] is True
    bajo_p, alto_p = pea["rango_personas_dia"]
    assert 0 < bajo_p < alto_p
    assert 0 <= pea["nivel"] <= 100
    # Sin vialidades ni población no se finge un rango de 0–0.
    vacio = proxy_vehicular([], poblacion_radio=0)
    assert vacio["rango_vehiculos_dia"] is None
    assert vacio["nivel"] is None
    assert "Sin datos" in vacio["etiqueta"]


# -------------------------------------------------------- anclas y Huff --
def test_anclas_deteccion_y_efecto_huff():
    establecimientos = [
        {"nombre": "Farmacias del Ahorro", "scian_code": "464111",
         "distancia_m": 200.0},
        {"nombre": "OXXO Roma", "scian_code": "462112", "distancia_m": 150.0},
        {"nombre": "BBVA", "scian_code": "522110", "distancia_m": 900.0},
        {"nombre": "Café Toscano", "scian_code": "722515",
         "distancia_m": 100.0},
        # Falsos positivos históricos por substring: no son anclas.
        {"nombre": "Subproductos Lácteos", "scian_code": "311830",
         "distancia_m": 50.0},
        {"nombre": "Extraordinario Café", "scian_code": "722515",
         "distancia_m": 60.0},
    ]
    anclas = detectar_anclas(establecimientos)
    # BBVA queda fuera: 900 m > radio de efecto de banco (400 m).
    assert [a["tipo"] for a in anclas] == ["conveniencia", "farmacia_descuento"]
    atractivo = 0.7
    efectivo = aplicar_efecto_ancla(atractivo, anclas)
    assert efectivo == pytest.approx(atractivo * (1 + 0.20 + 0.30))
    competidores = [(0.5, 0.3)]
    assert p_ij(efectivo, 0.2, competidores) > p_ij(atractivo, 0.2, competidores)
    # Sin anclas el resultado no cambia (compatibilidad con tests previos).
    assert aplicar_efecto_ancla(atractivo, []) == atractivo


# -------------------------------------------- compute con anclas/TAM ficha --
class SesionAnalisisFake:
    """Sesión fake para compute_location_analysis, ruteada por SQL."""

    def __init__(self, con_anclas=True):
        self._con_anclas = con_anclas

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "/* anclas */" in sql:
            filas = ([("Farmacias del Ahorro", "464111", 200.0)]
                     if self._con_anclas else [])
            return ResultadoFake(all_rows=filas)
        if "JOIN prod.cat_scian" in sql:  # Huff: antes que base_attractiveness
            return ResultadoFake(all_rows=[(0.5, 300.0)])
        if "base_attractiveness" in sql:
            return ResultadoFake(first_row=(0.7, 2.0))
        if "description FROM prod.cat_scian" in sql:
            return ResultadoFake(first_row=("Cafeterías",))
        if "COUNT(*)" in sql:
            return ResultadoFake(scalar_val=2)
        if "SUM(pob_30_59)" in sql:
            return ResultadoFake(scalar_val=5000)
        raise RuntimeError(f"SQL no esperado en fake: {sql[:80]}")


def test_compute_aplica_anclas_y_tam_de_ficha():
    db = SesionAnalisisFake(con_anclas=True)
    r = analysis_mod.compute_location_analysis(
        db, "sushi", "722511", 19.4195, -99.1627, [1000, 2000],
    )
    assert len(r["anclas"]) == 1
    assert r["huff"]["multiplicador_ancla"] == pytest.approx(1.30)
    assert r["huff"]["atractivo_efectivo"] == pytest.approx(0.7 * 1.30, abs=1e-3)
    # Ficha de sushi: gasto mensual $320 → $3,840/año.
    assert r["tam_supuestos"]["gasto_pc_mxn_anual"] == 3840.0

    r_sin = analysis_mod.compute_location_analysis(
        SesionAnalisisFake(con_anclas=False), "sushi", "722511",
        19.4195, -99.1627, [1000, 2000],
    )
    assert r_sin["huff"]["multiplicador_ancla"] == 1.0
    assert r["huff"]["cuota_punto"] > r_sin["huff"]["cuota_punto"]


def test_compute_tam_override_gana_sobre_ficha():
    r = analysis_mod.compute_location_analysis(
        SesionAnalisisFake(con_anclas=False), "sushi", "722511",
        19.4195, -99.1627, [1000],
        tam_overrides={"gasto_promedio_mensual": 100.0, "f_pen": 0.5},
    )
    assert r["tam_supuestos"]["gasto_pc_mxn_anual"] == 1200.0
    assert r["tam_supuestos"]["f_pen"] == 0.5


# ------------------------------------------------------ contexto + payload --
_AGEB_ROW = (24000, 12500, 11500, 3600, 5300, 11000, 3800, 300,
             10800, 9800, 2.45, 88.0, 80.0, 55.0)
_DENUE_ROWS = [
    ("Café Toscano", "722515", 19.4195, -99.1620, True, 120.0),
    ("Café Roma", "722515", 19.4200, -99.1610, True, 300.0),
    ("Farmacias del Ahorro", "464111", 19.4190, -99.1630, True, 250.0),
    ("OXXO Condesa", "462112", 19.4185, -99.1625, True, 180.0),
    ("Restaurante Rosetta", "722511", 19.4198, -99.1615, True, 400.0),
    ("BBVA Roma", "522110", 19.4205, -99.1605, True, 500.0),
    ("Primaria Benito Juárez", "611121", 19.4180, -99.1640, True, 600.0),
    ("Gym 24 Horas", "713940", 19.4210, -99.1600, True, 700.0),
    ("Pemex Gasolinera", "468411", 19.4220, -99.1590, True, 900.0),
]
_COMP_ROWS = [
    ("Café Toscano", 19.4195, -99.1620, True, 120.0),
    ("Café Roma", 19.4200, -99.1610, True, 300.0),
]


class SesionContextoFake:
    """Sesión fake del contexto: responde por marcador de consulta."""

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "ageb_agg" in sql:
            return ResultadoFake(first_row=_AGEB_ROW)
        if "nse_banda" in sql:
            return ResultadoFake(all_rows=[
                ("Medio a medio alto", 15000), ("Alto", 9000),
            ])
        if "denue_radio" in sql:
            return ResultadoFake(all_rows=list(_DENUE_ROWS))
        if "denue_total" in sql:
            return ResultadoFake(scalar_val=len(_DENUE_ROWS))
        if "competencia_lista" in sql:
            return ResultadoFake(all_rows=list(_COMP_ROWS))
        if "isocrona_pob" in sql:
            return ResultadoFake(scalar_val=5000)
        if "isocrona_comp" in sql:
            return ResultadoFake(scalar_val=3)
        if "knowledge_editorial" in sql:
            return ResultadoFake(first_row=None)
        raise RuntimeError(f"SQL no esperado en fake: {sql[:80]}")


def test_contexto_y_payload_14_secciones(monkeypatch):
    monkeypatch.setattr(context_mod, "fetch_isochrones", lambda lat, lon: [{
        "modo": "peaton", "modo_real": "pedestrian", "costing": "pedestrian",
        "minutos": 5, "alcance": "isocrona",
        "geometria": {"type": "Polygon", "coordinates": []},
    }])
    monkeypatch.setattr(context_mod, "fetch_vialidades", lambda lat, lon, radio_m=2000: [
        {"nombre": "Insurgentes Sur", "tipo": "primary", "distancia_m": 150.0},
        {"nombre": "Álvaro Obregón", "tipo": "secondary", "distancia_m": 320.0},
    ])
    analisis = {
        "giro": "cafetería", "scian": "722515",
        "anillos": [
            {"radio_m": 1000, "competencia": 2, "demanda_pob_30_59": 6000.0,
             "ism": 2000.0, "ism_banda": "oceano_azul",
             "fuente_demanda": "observada"},
            {"radio_m": 2000, "competencia": 5, "demanda_pob_30_59": 11000.0,
             "ism": 1833.3, "ism_banda": "oceano_azul",
             "fuente_demanda": "observada"},
        ],
        "tam_mxn": 1000000.0, "tam_rango": (750000.0, 1250000.0),
        "huff": {"cuota_punto": 0.3, "rango_cuota": [0.2, 0.4],
                 "alpha": 1.0, "lambda": 2.0},
        "advertencias": [], "anclas": [],
    }
    ctx = context_mod.build_report_context(
        SesionContextoFake(), giro="cafetería", scian="722515",
        lat=19.4195, lon=-99.1627, radios=[1000, 2000], analisis=analisis,
        etiqueta_ubicacion="Roma Norte, Cuauhtémoc, Ciudad de México",
        con_geocoding=True,
    )
    # Claves clave del ctx pobladas.
    assert ctx["demanda"]["poblacion_total"] == 24000
    assert len(ctx["demanda"]["segmentos"]) == 4
    assert ctx["hogares"]["viviendas_habitadas"] == 9800
    assert ctx["hogares"]["pct_internet"] == 88.0
    assert "Medio a medio alto" in ctx["nse_etiqueta"]
    assert "AMAI 2024" in ctx["nse_etiqueta"]
    assert ctx["entorno"]["total_negocios"] == 9
    assert ctx["competencia_anillo_1_2_km"] == 3
    assert len(ctx["competencia_lista"]) == 2
    assert ctx["competencia_lista"][0]["estado"] == "PARECE ACTIVO"
    assert ctx["atractores"]
    assert ctx["atractores"][0]["url_maps"].startswith(
        "https://www.google.com/maps/search/?api=1&query="
    )
    assert [a["tipo"] for a in ctx["anclas"]] == [
        "conveniencia", "farmacia_descuento",
    ]
    assert ctx["isocronas"][0]["poblacion"] == 5000
    assert ctx["isocronas"][0]["competidores"] == 3
    assert ctx["movilidad"]["vehicular"]["estimado"] is True
    assert ctx["perfil_editorial"]  # de la ficha de cafeterías
    assert ctx["delivery"]["aplica"] is True

    ctx.update({"titulo": "Análisis de prueba", "supuestos": [],
                "ediciones": [], "model_version": "1.0.0"})
    payload = build_location_report(ctx)
    # Las 14 secciones del payload, pobladas.
    assert payload["cabecera"]["ubicacion"].startswith("Roma Norte")
    assert payload["veredicto"]["decision"]
    assert payload["perfil_cliente"]["editorial"]
    assert payload["clientes_zona"]["poblacion_total"] == 24000
    assert len(payload["clientes_zona"]["segmentos"]) == 4
    assert payload["hogares_familias"]["viviendas_habitadas"] == 9800
    assert payload["atractores_trafico"]["items"]
    assert payload["competencia"]["lista"]
    assert payload["competencia"]["anillo_exterior"] == 3
    assert payload["mapas"]["centro"] == {"lat": 19.4195, "lon": -99.1627}
    assert payload["entorno_comercial"]["total_negocios"] == 9
    assert len(payload["entorno_comercial"]["categorias"]) == 9
    detalle = payload["poblacion_viviendas"]["detalle"]
    assert detalle["grupos_edad"]["30_59"] == 11000
    assert detalle["por_sexo"]["femenina"] == 12500
    mov = payload["movimiento_acceso"]
    assert "Medio a medio alto" in mov["nse_etiqueta"]
    assert mov["vialidades"] and mov["movilidad"]["vehicular"]["estimado"]
    assert payload["area_alcance_tiempo"]["isocronas"]
    assert payload["area_alcance_tiempo"]["alcance_tipo"] == "isocronas"
    assert payload["modelos"]["tam"]["tam_mxn_anual"] == 1000000.0
    fuentes = payload["fuentes_datos"]["fuentes"]
    assert any("INEGI Censo 2020" in f["fuente"] for f in fuentes)
    assert any("DENUE" in f["fuente"] for f in fuentes)
    assert payload["metodologia_advertencias"] is not None
    assert payload["plan_contacto"] is not None
    assert payload["datos_sector"]["ticket_promedio"] == 95.0
    assert payload["delivery"]["aplica"] is True
    assert payload["punto_equilibrio"]["ventas_equilibrio_mensual"] > 0
    assert payload["negocios_ancla"]["items"]


# ------------------------------ editorial knowledge_facts (regresión ADR-010) --
def test_editorial_knowledge_facts_sin_calificar_prod():
    """Regresión ADR-010: knowledge_facts vive en el esquema por defecto
    (public; migración 0003). El SQL no debe llevar prefijo ``prod.`` o
    PostgreSQL aborta la transacción y el 500 aparece después, en el
    commit del reporte, con traceback engañoso."""
    capturado = {}

    class SesionEditorialFake:
        def execute(self, stmt, params=None):
            capturado["sql"] = str(stmt)
            return ResultadoFake(first_row=None)

    assert context_mod._perfil_editorial(SesionEditorialFake(), "cafetería", None) is None
    assert "knowledge_editorial" in capturado["sql"]
    assert "prod.knowledge_facts" not in capturado["sql"]


def test_editorial_falla_sql_deja_sesion_limpia():
    """Regresión ADR-010: un error SQL que el flujo decide tragarse debe
    hacer rollback o la sesión queda envenenada y toda sentencia
    posterior del request muere con ``InFailedSqlTransaction``."""
    class SesionEditorialRota:
        def __init__(self):
            self.rollbacks = 0

        def execute(self, stmt, params=None):
            raise RuntimeError("SQL no esperado en fake")

        def rollback(self):
            self.rollbacks += 1

    sesion = SesionEditorialRota()
    assert context_mod._perfil_editorial(sesion, "cafetería", None) is None
    assert sesion.rollbacks == 1


# ------------------------------------------------- POST /reports completo --
class _QueryGenericaFake:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def all(self):
        return []


class SesionReporteFake(SesionAnalisisFake):
    """Fake combinada: análisis real + contexto + persistencia de Report."""

    def __init__(self):
        super().__init__(con_anclas=True)
        self.reporte_guardado = None

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "data_editions" in sql:
            return ResultadoFake(all_rows=[])
        if "ageb_agg" in sql:
            return ResultadoFake(first_row=_AGEB_ROW)
        if "nse_banda" in sql:
            return ResultadoFake(all_rows=[("Medio a medio alto", 15000)])
        if "denue_radio" in sql:
            return ResultadoFake(all_rows=list(_DENUE_ROWS))
        if "denue_total" in sql:
            return ResultadoFake(scalar_val=len(_DENUE_ROWS))
        if "competencia_lista" in sql:
            return ResultadoFake(all_rows=list(_COMP_ROWS))
        if "isocrona" in sql or "knowledge_editorial" in sql:
            return ResultadoFake(first_row=None, scalar_val=0)
        return super().execute(stmt, params)

    def get(self, _modelo, _id):
        return None

    def add(self, obj):
        if isinstance(obj, Report):
            if obj.report_id is None:
                obj.report_id = uuid.uuid4()
            if obj.created_at is None:
                obj.created_at = datetime.now(timezone.utc)
            self.reporte_guardado = obj

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def query(self, _modelo):
        return _QueryGenericaFake()


def test_post_reports_payload_completo(monkeypatch):
    monkeypatch.setattr(reports_mod, "nominatim_reverse",
                        lambda lat, lon: _REVERSE_ROMA)
    monkeypatch.setattr(context_mod, "fetch_isochrones", lambda lat, lon: [])
    monkeypatch.setattr(context_mod, "fetch_vialidades",
                        lambda lat, lon, radio_m=2000: [
                            {"nombre": "Insurgentes Sur", "tipo": "primary",
                             "distancia_m": 150.0},
                        ])
    cliente = _cliente(reports_mod, sesion=SesionReporteFake())
    res = cliente.post("/api/v1/reports", json={
        "title": "Análisis Roma", "giro": "cafetería", "scian": "722515",
        "lat": 19.4195, "lon": -99.1627, "radios": [1000, 2000],
    })
    assert res.status_code == 201
    payload = res.json()["payload"]
    # La etiqueta ya no es «lat, lon» crudo: viene del reverse.
    assert payload["cabecera"]["ubicacion"].startswith("Roma Norte")
    assert payload["clientes_zona"]["poblacion_total"] == 24000
    assert payload["hogares_familias"]["viviendas_habitadas"] == 9800
    assert payload["entorno_comercial"]["total_negocios"] == 9
    assert payload["competencia"]["lista"]
    assert payload["atractores_trafico"]["items"]
    assert "Medio a medio alto" in payload["movimiento_acceso"]["nse_etiqueta"]
    # Sin Valhalla (mock vacío) el alcance se etiqueta como radios: honesto.
    assert payload["area_alcance_tiempo"]["alcance_tipo"] == "radios"
    assert payload["negocios_ancla"]["items"]  # efecto ancla también en Huff
    assert res.json()["verdict"] == payload["veredicto"]["decision"]


# ----------------------------------------------------------------- shares --
class _QueryShareFake:
    def __init__(self, sesion):
        self._sesion = sesion

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._sesion.share_actual


class SesionSharesFake:
    """Sesión fake de shares: get por dict + query de un solo share."""

    def __init__(self, reporte=None):
        self._reportes = {reporte.report_id: reporte} if reporte else {}
        self.share_actual: ReportShare | None = None
        self.commits = 0

    def get(self, modelo, id_):
        if modelo is Report:
            return self._reportes.get(id_)
        return None

    def add(self, obj):
        if isinstance(obj, ReportShare):
            self.share_actual = obj

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        pass

    def query(self, modelo):
        return _QueryShareFake(self)

    def execute(self, *args, **kwargs):
        raise RuntimeError("sin BD real en tests")


def _reporte_fake():
    return SimpleNamespace(
        report_id=uuid.uuid4(), title="Reporte Roma", verdict="AVANZAR",
        payload={"veredicto": {"decision": "AVANZAR"}},
        created_at=datetime.now(timezone.utc),
    )


def test_shares_crear_leer_revocar():
    reporte = _reporte_fake()
    cliente = _cliente(reports_mod, sesion=SesionSharesFake(reporte))

    res = cliente.post(f"/api/v1/reports/{reporte.report_id}/share",
                       json={"dias": 30})
    assert res.status_code == 201
    cuerpo = res.json()
    token = cuerpo["token"]
    assert cuerpo["url"] == f"/r/{token}"
    assert cuerpo["expira_en"]

    res = cliente.get(f"/api/v1/reports/shared/{token}")
    assert res.status_code == 200
    assert res.json()["payload"] == {"veredicto": {"decision": "AVANZAR"}}
    assert res.json()["report_id"] == str(reporte.report_id)

    res = cliente.delete(f"/api/v1/reports/{reporte.report_id}/share/{token}")
    assert res.status_code == 204

    res = cliente.get(f"/api/v1/reports/shared/{token}")
    assert res.status_code == 404


def test_shares_token_invalido_404_y_reporte_inexistente():
    cliente = _cliente(reports_mod, sesion=SesionSharesFake())
    assert cliente.get("/api/v1/reports/shared/no-existe").status_code == 404
    res = cliente.post(f"/api/v1/reports/{uuid.uuid4()}/share", json={})
    assert res.status_code == 404


# ----------------------------------------------------------------- compare --
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


class SesionCompareFake:
    def __init__(self, investigaciones=None):
        self._investigaciones = investigaciones or {}

    def get(self, _modelo, id_):
        return self._investigaciones.get(id_)

    def execute(self, *args, **kwargs):
        raise RuntimeError("sin BD real en tests")


def _instalar_analisis_fijo(monkeypatch):
    def fake(db, giro=None, scian=None, lat=None, lon=None, radios=None):
        return _ANALISIS_FIJO

    monkeypatch.setattr(analysis_mod, "compute_location_analysis", fake)


def _investigacion(id_, **extras):
    datos = {
        "investigation_id": id_, "title": "Investigación de prueba",
        "territory_kind": "point_buffers", "center_lat": 19.419,
        "center_lon": -99.161, "radii_m": [1000, 2000],
        "params": {"giro": "cafetería", "scian": "722515"},
    }
    datos.update(extras)
    return SimpleNamespace(**datos)


def test_compare_puntos_directos(monkeypatch):
    _instalar_analisis_fijo(monkeypatch)
    cliente = _cliente(analysis_mod, sesion=SesionCompareFake())
    res = cliente.post("/api/v1/analysis/compare", json={"items": [
        {"lat": 19.4195, "lon": -99.1627, "giro": "cafetería",
         "etiqueta": "Roma Norte"},
        {"lat": 19.4326, "lon": -99.1332, "giro": "cafetería"},
    ]})
    assert res.status_code == 200
    items = res.json()["items"]
    assert items[0]["nombre"] == "Roma Norte"
    assert items[0]["territorio"] == "punto_directo"
    assert items[0]["ism"] == 357.1
    assert items[1]["id"].startswith("punto:")


def test_compare_limite_6_con_items(monkeypatch):
    _instalar_analisis_fijo(monkeypatch)
    cliente = _cliente(analysis_mod, sesion=SesionCompareFake())
    punto = {"lat": 19.4195, "lon": -99.1627, "giro": "cafetería"}
    res = cliente.post("/api/v1/analysis/compare",
                       json={"items": [dict(punto) for _ in range(6)]})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 6
    res = cliente.post("/api/v1/analysis/compare",
                       json={"items": [dict(punto) for _ in range(7)]})
    assert res.status_code == 422


def test_compare_mixto_investigacion_y_punto(monkeypatch):
    _instalar_analisis_fijo(monkeypatch)
    id_inv = uuid.uuid4()
    sesion = SesionCompareFake({id_inv: _investigacion(id_inv)})
    cliente = _cliente(analysis_mod, sesion=sesion)
    res = cliente.post("/api/v1/analysis/compare", json={"items": [
        {"investigation_id": str(id_inv)},
        {"lat": 19.41, "lon": -99.17, "etiqueta": "Condesa"},
    ]})
    assert res.status_code == 200
    items = res.json()["items"]
    assert items[0]["id"] == str(id_inv)
    assert items[1]["territorio"] == "punto_directo"


# ------------------------------------------------------------ es_principal --
class _QueryInvFake:
    def __init__(self, sesion):
        self._sesion = sesion

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._sesion.investigaciones.values())


class SesionPatchFake:
    def __init__(self, investigaciones):
        self.investigaciones = investigaciones
        self.commits = 0

    def get(self, _modelo, id_):
        return self.investigaciones.get(id_)

    def query(self, _modelo):
        return _QueryInvFake(self)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        pass

    def execute(self, *args, **kwargs):
        raise RuntimeError("sin BD real en tests")


def _inv_completa(id_, user_id="guest", es_principal=False):
    return SimpleNamespace(
        investigation_id=id_, user_id=user_id, title="Inv",
        investigation_type="location_viability", vertical=None,
        territory_kind="point_buffers", center_lat=19.419,
        center_lon=-99.161, radii_m=[1000, 2000], params={}, scores=None,
        verdict=None, status="completed", es_principal=es_principal,
        created_at=datetime.now(timezone.utc),
    )


def test_patch_es_principal_desmarca_las_demas():
    id_1, id_2 = uuid.uuid4(), uuid.uuid4()
    inv1 = _inv_completa(id_1, es_principal=True)
    inv2 = _inv_completa(id_2, es_principal=False)
    sesion = SesionPatchFake({id_1: inv1, id_2: inv2})
    cliente = _cliente(investigations_mod, sesion=sesion)
    res = cliente.patch(f"/api/v1/investigations/{id_2}",
                        json={"es_principal": True})
    assert res.status_code == 200
    assert res.json()["es_principal"] is True
    assert inv2.es_principal is True
    assert inv1.es_principal is False  # solo una principal por usuario
    assert sesion.commits == 1


def test_patch_es_principal_404():
    cliente = _cliente(investigations_mod, sesion=SesionPatchFake({}))
    res = cliente.patch(f"/api/v1/investigations/{uuid.uuid4()}",
                        json={"es_principal": True})
    assert res.status_code == 404
