"""Tests del score unificado GEIS × Radar (fusión §5 del blueprint)."""
import math

import pytest

from app.analytics.scoring_unificado import (
    PESOS_BIOKOOL,
    PESOS_GENERICO,
    linea_recomendada,
    score_unificado,
)

BASE = {
    "idt": 0.8, "tamano": 0.5, "acceso": 0.7, "densidad": 0.6, "contacto": 0.5,
}


def test_pesos_biokool_suman_uno():
    assert math.isclose(sum(PESOS_BIOKOOL.values()), 1.0)


def test_pesos_generico_suman_uno_y_son_espaciales():
    assert math.isclose(sum(PESOS_GENERICO.values()), 1.0)
    assert set(PESOS_GENERICO) == {"idt", "tamano", "acceso", "densidad", "contacto"}


def test_temp_mayor_30_normaliza_a_uno():
    r = score_unificado({**BASE, "temp_zona": 35.5})
    assert r["x"]["temp"] == 1.0


def test_temp_menor_30_normaliza_a_cero():
    r = score_unificado({**BASE, "temp_zona": 24.0})
    assert r["x"]["temp"] == 0.0


def test_senal_verdadera_normaliza_a_uno():
    r = score_unificado({**BASE, "senal": True})
    assert r["x"]["senal"] == 1.0


def test_senal_falsa_normaliza_a_cero():
    r = score_unificado({**BASE, "senal": False})
    assert r["x"]["senal"] == 0.0


def test_score_nunca_supera_100():
    r = score_unificado({
        "idt": 1.0, "tamano": 1.0, "acceso": 1.0, "densidad": 1.0,
        "contacto": 1.0, "temp_zona": 45.0, "senal": True, "linkedin": 1.0,
    })
    assert 0 <= r["score"] <= 100


def test_score_sube_con_componentes_conductuales():
    sin = score_unificado({**BASE})
    con = score_unificado({**BASE, "temp_zona": 38.0, "senal": True})
    assert con["score"] > sin["score"]


def test_linea_marzo_koolkat():
    assert linea_recomendada(3) == "koolkat"


def test_linea_febrero_koolkat():
    assert linea_recomendada(2, "gasolinera") == "koolkat"


def test_linea_noviembre_gasolinera_solar():
    assert linea_recomendada(11, "Gasolinera Pemex") == "solar"


def test_linea_diciembre_estacionamiento_solar():
    assert linea_recomendada(12, "Estacionamiento público") == "solar"


def test_linea_agosto_evaporativa():
    assert linea_recomendada(8) == "evaporativa"


def test_linea_enero_sin_giro_evaporativa():
    assert linea_recomendada(1, None) == "evaporativa"


def test_linea_enero_sin_giro_sensible_a_mayusculas():
    assert linea_recomendada(10, "PLAZA COMERCIAL ANDARES") == "solar"


def test_componentes_none_se_excluyen():
    r = score_unificado({**BASE, "contacto": None, "linkedin": None})
    assert "contacto" not in r["componentes_usados"]
    assert "linkedin" not in r["componentes_usados"]
    assert r["score"] >= 0


def test_vertical_generico_ignora_conductuales():
    r = score_unificado(
        {**BASE, "temp_zona": 40.0, "senal": True, "linkedin": 0.9},
        vertical="generico",
    )
    assert r["vertical"] == "generico"
    assert set(r["componentes_usados"]).issubset(
        {"idt", "tamano", "acceso", "densidad", "contacto"}
    )
    assert "temp" not in r["componentes_usados"]
    assert "senal" not in r["componentes_usados"]


def test_vertical_generico_igual_sin_conductuales():
    con_conductuales = score_unificado(
        {**BASE, "temp_zona": 40.0}, vertical="generico")
    solo_espaciales = score_unificado({**BASE}, vertical="generico")
    assert con_conductuales["score"] == solo_espaciales["score"]


def test_sin_componentes_disponibles_falla():
    with pytest.raises(ValueError):
        score_unificado({"idt": None, "tamano": None})
