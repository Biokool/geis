"""Tests de las fórmulas analíticas del SRS §3 (casos numéricos verificados)."""
import math

import pytest

from app.analytics import (
    accesibilidad_logistica,
    b2b_score,
    captura,
    completitud_contacto,
    demanda_capturada,
    e_estrato,
    idt,
    ism,
    ism_band,
    p_ij,
    p_ij_rango,
    rango,
    tam,
)
from app.geo.ops import buffer_m as geo_buffer_m
from app.reports.builder import build_location_report, decidir_veredicto


# ---------------------------------------------------------------- ISM §3.1
def test_ism_ejemplo_roma_norte():
    """Caso del SRS: D=13,306, O=33 → ISM = 391.4."""
    assert ism(13306, 33) == pytest.approx(391.4, abs=0.05)


def test_ism_suavizado_laplace_sin_competencia():
    """Sin competencia el ISM equivale a 'demanda por competidor potencial'."""
    assert ism(1000, 0) == 1000.0


def test_ism_rechaza_negativos():
    with pytest.raises(ValueError):
        ism(-1, 5)
    with pytest.raises(ValueError):
        ism(10, -2)


def test_ism_band_caso_srs():
    """ISM 391.4 con P50=280, P90=520 → 'equilibrado tendiendo a azul'."""
    assert ism_band(391.4, 280, 520) == "equilibrado"


def test_ism_band_cuatro_bandas():
    assert ism_band(600, 280, 520, p10=100) == "oceano_azul"
    assert ism_band(300, 280, 520, p10=100) == "equilibrado"
    assert ism_band(150, 280, 520, p10=100) == "competido"
    assert ism_band(50, 280, 520, p10=100) == "oceano_rojo"


# --------------------------------------------------------------- Huff §3.2
def test_huff_ejemplo_srs():
    """Caso del SRS: candidato A=0.7 a 200 m vs k1 (0.9, 500 m) y k2 (0.5, 1 km).

    j: 0.7/0.2² = 17.5; k1: 0.9/0.5² = 3.6; k2: 0.5/1.0² = 0.5; Σ = 21.6.
    """
    p = p_ij(0.7, 0.2, [(0.9, 0.5), (0.5, 1.0)], alpha=1.0, lambda_=2.0)
    assert p == pytest.approx(17.5 / 21.6, rel=1e-9)
    assert p == pytest.approx(0.81, abs=0.005)


def test_huff_suma_uno_con_candidato_incluido():
    """Las probabilidades sobre todos los puntos suman 1."""
    comps = [(0.9, 0.5), (0.5, 1.0)]
    p_j = p_ij(0.7, 0.2, comps)
    p_k1 = p_ij(0.9, 0.5, [(0.7, 0.2), (0.5, 1.0)])
    p_k2 = p_ij(0.5, 1.0, [(0.7, 0.2), (0.9, 0.5)])
    assert p_j + p_k1 + p_k2 == pytest.approx(1.0)


def test_huff_rango_sensibilidad():
    p_min, p_punto, p_max = p_ij_rango(0.7, 0.2, [(0.9, 0.5)], lambda_=2.0, delta=0.5)
    assert p_min <= p_punto <= p_max


def test_huff_distancia_cero_rechazada():
    with pytest.raises(ValueError):
        p_ij(0.7, 0.0, [])


def test_demanda_capturada():
    assert demanda_capturada([(0.8, 1000), (0.5, 2000)]) == pytest.approx(1800.0)


# ---------------------------------------------------------------- TAM §3.3
def test_tam_ejemplo_srs():
    """Caso del SRS: 13,306 × 2,400 × 1.15 × 0.45.

    Nota: el SRS publica $16,524,906; la aritmética exacta da $16,526,052
    (diferencia de redondeo del documento, <0.01%).
    """
    assert tam(13306, 2400, 1.15, 0.45) == pytest.approx(16526052.0, rel=1e-9)


def test_tam_rango_mas_menos_25():
    t = tam(13306, 2400, 1.15, 0.45)
    lo, hi = rango(t)
    assert lo == pytest.approx(t * 0.75)
    assert hi == pytest.approx(t * 1.25)


def test_tam_rango_custom():
    lo, hi = rango(100.0, pct=0.10)
    assert lo == pytest.approx(90.0)
    assert hi == pytest.approx(110.0)


def test_tam_captura_huff():
    """Captura = TAM × cuota Huff (ejemplo SRS: 12% → ≈$1.98M)."""
    t = tam(13306, 2400, 1.15, 0.45)
    assert captura(t, 0.12) == pytest.approx(t * 0.12)


def test_tam_rechaza_f_pen_fuera_de_rango():
    with pytest.raises(ValueError):
        tam(1000, 2400, 1.0, 1.5)


# ---------------------------------------------------------------- IDT §3.4
def test_e_estrato_escala_srs():
    assert e_estrato(1) == 0.10
    assert e_estrato(2) == 0.25
    assert e_estrato(3) == 0.40
    assert e_estrato(4) == 0.55
    assert e_estrato(5) == 0.70
    assert e_estrato(6) == 0.85
    assert e_estrato(7) == 1.00
    with pytest.raises(ValueError):
        e_estrato(8)


def test_idt_ejemplo_srs():
    """Planta alimentaria (I=0.9), estrato 101–250 (E=0.85), clima 0.8, antigüedad NA.

    100 × (0.35×0.85 + 0.30×0.9 + 0.20×0.8 + 0.15×0.5) = 80.25 → 80.
    """
    r = idt(6, 0.9, 0.8, None)
    assert r["idt"] == pytest.approx(80.25, rel=1e-9)
    assert r["datos_faltantes"] == ["antiguedad"]
    assert r["entradas"]["antiguedad"] == 0.5  # neutro con bandera


def test_idt_desglose_suma_100_veces_componentes():
    r = idt(7, 1.0, 1.0, 1.0)
    assert r["idt"] == pytest.approx(100.0)
    assert sum(r["componentes"].values()) == pytest.approx(100.0)


def test_idt_pesos_deben_sumar_uno():
    with pytest.raises(ValueError):
        idt(3, 0.5, 0.5, 0.5, pesos=(0.5, 0.5, 0.5, 0.5))


def test_idt_pesos_custom():
    r = idt(1, 0.0, 0.0, 0.0, pesos=(0.25, 0.25, 0.25, 0.25))
    assert r["idt"] == pytest.approx(100 * 0.25 * 0.10)


# ------------------------------------------------------------- Score §3.5
def test_b2b_score_ejemplo():
    componentes = {
        "idt": 0.80, "tamano": 0.85, "accesibilidad": 0.90,
        "densidad": 0.60, "contacto": 0.66,
    }
    r = b2b_score(componentes)
    esperado = 100 * (0.40 * 0.80 + 0.20 * 0.85 + 0.15 * 0.90 + 0.15 * 0.60 + 0.10 * 0.66)
    assert r["score"] == pytest.approx(round(esperado, 2))
    assert set(r["desglose"]) == set(componentes)
    assert sum(r["desglose"].values()) == pytest.approx(r["score"])


def test_b2b_score_renormaliza_sin_componentes_faltantes():
    """Solo sobre componentes disponibles: se divide entre Σ w_m usados."""
    r = b2b_score({"idt": 1.0, "tamano": 1.0})
    assert r["score"] == pytest.approx(100.0)
    assert r["componentes_usados"] == ["idt", "tamano"]


def test_b2b_score_rechaza_vacio_y_desconocidos():
    with pytest.raises(ValueError):
        b2b_score({"idt": None})
    with pytest.raises(ValueError):
        b2b_score({"otro": 0.5})


def test_completitud_contacto():
    assert completitud_contacto(True, True, True) == pytest.approx(1.0)
    assert completitud_contacto(True, False, False) == pytest.approx(0.33)
    assert completitud_contacto(False, False, False) == 0.0


def test_accesibilidad_logistica():
    assert accesibilidad_logistica(0) == 1.0
    assert accesibilidad_logistica(5) == pytest.approx(0.5)
    assert accesibilidad_logistica(20) == 0.0  # tope en 10 km


# --------------------------------------------------------------- Geo §4.4
def test_buffer_m_area_aproximada():
    """El buffer geodésico de 1 km ≈ π·r² (tolerancia 1%)."""
    poly = geo_buffer_m(19.41, -99.16, 1000, segments=128)
    from pyproj import Geod

    area_m2, _ = Geod(ellps="WGS84").geometry_area_perimeter(poly)
    assert abs(area_m2) == pytest.approx(math.pi * 1e6, rel=0.01)


def test_buffer_m_rechaza_radio_invalido():
    with pytest.raises(ValueError):
        geo_buffer_m(19.41, -99.16, 0)


# ----------------------------------------------------------- Reporte §6.5
def test_decidir_veredicto():
    azules = [{"ism_banda": "oceano_azul"}, {"ism_banda": "oceano_azul"}]
    v, conf, factores = decidir_veredicto(azules)
    assert v == "AVANZAR" and factores

    rojos = [{"ism_banda": "oceano_rojo"}, {"ism_banda": "competido"}]
    v, _, _ = decidir_veredicto(rojos)
    assert v == "EXPLORAR_OTRA_ZONA"


def test_build_location_report_13_secciones():
    payload = build_location_report({
        "titulo": "Análisis para Cafetería",
        "giro": "cafetería", "scian": "722515",
        "lat": 19.419, "lon": -99.161, "radios": [1000, 2000],
        "anillos": [
            {"radio_m": 1000, "competencia": 33, "demanda_pob_30_59": 13306,
             "ism": 391.4, "ism_banda": "equilibrado", "fuente_demanda": "observada"},
        ],
        "tam_mxn": 16526052.0, "tam_rango": (12394539.0, 20657565.0),
        "huff": {"cuota_punto": 0.12, "rango_cuota": [0.09, 0.16], "alpha": 1.0, "lambda": 2.5},
        "ediciones": ["DENUE:DENUE_SEED_2026"],
    })
    secciones = [
        "veredicto", "perfil_cliente", "clientes_zona", "hogares_familias",
        "atractores_trafico", "competencia", "mapas", "entorno_comercial",
        "poblacion_viviendas", "movimiento_acceso", "area_alcance_tiempo",
        "modelos", "fuentes_datos", "metodologia_advertencias",
    ]
    for s in secciones:
        assert s in payload, f"falta la sección {s}"
    assert payload["veredicto"]["decision"] in ("AVANZAR", "NEGOCIAR", "EXPLORAR_OTRA_ZONA")
    assert payload["modelos"]["tam"]["advertencia"].startswith("El TAM es el tamaño del mercado")
