"""Fórmulas analíticas del SRS §3 como funciones puras y testeables."""
from app.analytics.huff import demanda_capturada, p_ij, p_ij_rango
from app.analytics.idt import ESTRATO_ESCALA, PESOS_DEFAULT as IDT_PESOS, e_estrato, idt
from app.analytics.ism import BANDAS, ism, ism_band, ism_descripcion
from app.analytics.scoring import (
    PESOS_DEFAULT as SCORE_PESOS,
    accesibilidad_logistica,
    b2b_score,
    completitud_contacto,
)
from app.analytics.tam import captura, rango, tam

__all__ = [
    "BANDAS",
    "ESTRATO_ESCALA",
    "IDT_PESOS",
    "SCORE_PESOS",
    "accesibilidad_logistica",
    "b2b_score",
    "captura",
    "completitud_contacto",
    "demanda_capturada",
    "e_estrato",
    "idt",
    "ism",
    "ism_band",
    "ism_descripcion",
    "p_ij",
    "p_ij_rango",
    "rango",
    "tam",
]
