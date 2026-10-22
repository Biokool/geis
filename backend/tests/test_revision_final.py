"""Tests de la revisión final del ecosistema GEIS × Biokool Radar.

Cubren los hallazgos de la auditoría backend:
- validación de pesos en ``b2b_score`` (score siempre en [0, 100]),
- casos borde de ISM/Huff (sin división por cero),
- ``linea_recomendada`` cubre los 12 meses y valida el rango,
- ``vertical`` desconocida en ``score_unificado`` falla fuerte,
- §14 ``plan_contacto`` en el builder + honestidad "dato no disponible",
- ``filas_a_csv`` (exportador puro del endpoint POST /leads/export).
"""
import csv
import io
import random

import pytest

from app.analytics import b2b_score
from app.analytics.huff import p_ij
from app.analytics.ism import ism, ism_band
from app.analytics.scoring_unificado import (
    linea_recomendada,
    score_unificado,
    sugerir_plan_contacto,
)
from app.api.v1.leads import filas_a_csv
from app.reports.builder import build_location_report


# ------------------------------------------------- b2b_score: pesos sanos
def test_b2b_score_rechaza_pesos_negativos():
    with pytest.raises(ValueError):
        b2b_score({"idt": 0.5, "tamano": 0.5}, pesos={"idt": 0.5, "tamano": -0.5})


def test_b2b_score_rechaza_suma_de_pesos_cero():
    with pytest.raises(ValueError):
        b2b_score({"idt": 0.5}, pesos={"idt": 0.0})


def test_b2b_score_siempre_en_0_100_fuzz():
    rng = random.Random(7)
    claves = ["idt", "tamano", "accesibilidad", "densidad", "contacto"]
    for _ in range(200):
        comp = {k: (rng.random() if rng.random() < 0.9 else None) for k in claves}
        if not any(v is not None for v in comp.values()):
            comp["idt"] = rng.random()
        r = b2b_score(comp)
        assert 0.0 <= r["score"] <= 100.0


# ------------------------------------------------- ISM/Huff: casos borde
def test_ism_oferta_cero_no_divide_entre_cero():
    assert ism(500, 0) == 500.0


def test_ism_band_fronteras():
    assert ism_band(520, 280, 520) == "oceano_azul"   # == P90
    assert ism_band(280, 280, 520) == "equilibrado"    # == P50
    assert ism_band(279.9, 280, 520) == "oceano_rojo"  # < P50 sin p10


def test_huff_denominador_cero_devuelve_cero():
    # Atractivo 0 en todos los puntos: denominador 0 → 0.0, no excepción.
    assert p_ij(0.0, 0.2, [(0.0, 0.5)]) == 0.0


def test_huff_distancia_competidor_cero_rechazada():
    with pytest.raises(ValueError):
        p_ij(0.7, 0.2, [(0.9, 0.0)])


# ------------------------------------------------- linea_recomendada / vertical
def test_linea_cubre_los_12_meses():
    lineas = {linea_recomendada(m) for m in range(1, 13)}
    assert lineas <= {"koolkat", "solar", "evaporativa"}
    # Cada mes devuelve exactamente una línea válida (sin huecos).
    for m in range(1, 13):
        assert linea_recomendada(m, "Taller mecánico") in lineas


def test_linea_mes_fuera_de_rango_falla():
    with pytest.raises(ValueError):
        linea_recomendada(0)
    with pytest.raises(ValueError):
        linea_recomendada(13)


def test_score_unificado_vertical_desconocida_falla():
    with pytest.raises(ValueError):
        score_unificado({"idt": 0.5}, vertical="inexistente")


# ------------------------------------------------- sugerir_plan_contacto (§14)
def test_plan_contacto_sin_giro_dato_no_disponible():
    r = sugerir_plan_contacto(None, temp_c=30.0, mes=5)
    assert r["estado"] == "dato no disponible"
    assert r["linea"] is None
    assert r["argumentos"] == []


def test_plan_contacto_linea_y_momento_calculados():
    r = sugerir_plan_contacto("Gasolinera Pemex", temp_c=33.5, mes=11)
    assert r["estado"] == "ok"
    assert r["linea"] == "solar"
    assert r["linea"] == linea_recomendada(11, "Gasolinera Pemex")
    assert r["motivo_linea"]
    assert len(r["argumentos"]) >= 2
    assert "inmediato" in r["momento"]  # ola de calor ≥ 32 °C


def test_plan_contacto_sin_temp_momento_honesto():
    r = sugerir_plan_contacto("Hotel", temp_c=None, mes=3)
    assert r["linea"] == "koolkat"
    assert "Sin dato de temperatura" in r["momento"]


def test_plan_contacto_consistente_con_linea_todo_el_anio():
    for m in range(1, 13):
        for giro in ["Gasolinera", "Hotel", "Taller mecánico", None]:
            r = sugerir_plan_contacto(giro, temp_c=28.0, mes=m)
            if giro is None:
                assert r["linea"] is None
            else:
                assert r["linea"] == linea_recomendada(m, giro)


# ------------------------------------------------- builder: 14 secciones
def _ctx_minimo(**extras):
    ctx = {
        "titulo": "Análisis de prueba",
        "giro": "cafetería",
        "lat": 19.419, "lon": -99.161,
        "anillos": [
            {"radio_m": 1000, "competencia": 33, "demanda_pob_30_59": 13306,
             "ism": 391.4, "ism_banda": "equilibrado"},
        ],
        "tam_mxn": 16526052.0, "tam_rango": (12394539.0, 20657565.0),
        "huff": {"cuota_punto": 0.12, "rango_cuota": [0.09, 0.16]},
    }
    ctx.update(extras)
    return ctx


def test_builder_incluye_plan_contacto_seccion_14():
    payload = build_location_report(_ctx_minimo(mes=11, temp_zona=33.0))
    assert "plan_contacto" in payload
    plan = payload["plan_contacto"]
    assert plan["estado"] == "ok"
    assert plan["linea"] in ("koolkat", "solar", "evaporativa")
    assert plan["argumentos"] and plan["momento"]


def test_builder_perfil_sin_editorial_dato_no_disponible():
    payload = build_location_report(_ctx_minimo())
    perfil = payload["perfil_cliente"]
    assert perfil["estado"] == "dato no disponible"
    assert perfil["editorial"] is None
    # Prohibido el placeholder quemado.
    assert "Texto editorial del perfil" not in str(payload)


def test_builder_perfil_con_editorial_la_respeta():
    payload = build_location_report(
        _ctx_minimo(perfil_editorial="El cliente típico busca café de especialidad.")
    )
    assert payload["perfil_cliente"]["editorial"].startswith("El cliente típico")


# ------------------------------------------------- filas_a_csv (export puro)
def _fila(i, estrato_ord=3, scian="722515"):
    return (
        f"SEED-{i:03d}", f"Negocio {i}", scian, "desc", "11 a 30",
        estrato_ord, "Cuauhtémoc", "5550000001" if i % 2 else None,
        None, None, 19.41, -99.16,
    )


def test_filas_a_csv_cabecera_y_scores_acotados():
    filas = [_fila(1), _fila(2, estrato_ord=6), _fila(3, estrato_ord=1)]
    texto = filas_a_csv(filas, {"722515": 0.25})
    lector = list(csv.DictReader(io.StringIO(texto)))
    assert len(lector) == 3
    assert lector[0]["denue_id"] == "SEED-001"
    for row in lector:
        assert 0.0 <= float(row["idt"]) <= 100.0
        assert 0.0 <= float(row["score"]) <= 100.0


def test_filas_a_csv_fila_invalida_no_tumba_export():
    filas = [_fila(1), _fila(2, estrato_ord=99)]  # estrato inválido
    texto = filas_a_csv(filas, {"722515": 0.25})
    lector = list(csv.DictReader(io.StringIO(texto)))
    assert len(lector) == 2
    assert lector[1]["idt"] in ("", None) or lector[1]["idt"] == ""


def test_filas_a_csv_vacio_solo_cabecera():
    texto = filas_a_csv([], {})
    assert texto.strip().splitlines() == [
        "denue_id,nombre,scian_code,scian_desc,estrato_texto,municipio,"
        "telefono,correo,sitio_web,lat,lon,idt,score"
    ]
