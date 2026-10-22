"""Estimación de ingresos potenciales / TAM — SRS §3.3.

El TAM territorial estima el gasto anual potencial del giro en el
territorio (MXN). Es el tamaño del pastel, no un pronóstico de ventas.
"""
from __future__ import annotations


def tam(pob_obj: float, gasto_pc: float, f_nse: float, f_pen: float) -> float:
    """TAM = P_obj × G_pc × F_nse × F_pen (MXN/año).

    :param pob_obj: población objetivo en el territorio.
    :param gasto_pc: gasto per cápita anual estimado en el giro (MXN).
    :param f_nse: factor de ajuste por nivel socioeconómico (0.6–1.4).
    :param f_pen: penetración del canal/formato (0–1).
    """
    for nombre, valor in (("pob_obj", pob_obj), ("gasto_pc", gasto_pc),
                          ("f_nse", f_nse), ("f_pen", f_pen)):
        if valor < 0:
            raise ValueError(f"{nombre} no puede ser negativo")
    if not 0 <= f_pen <= 1:
        raise ValueError("f_pen debe estar entre 0 y 1")
    return pob_obj * gasto_pc * f_nse * f_pen


def rango(tam_valor: float, pct: float = 0.25) -> tuple[float, float]:
    """Rango del TAM: ±pct por defecto (TAM-02: nunca cifra única en titulares)."""
    if not 0 <= pct < 1:
        raise ValueError("pct debe estar en [0, 1)")
    return (tam_valor * (1 - pct), tam_valor * (1 + pct))


def captura(tam_valor: float, p_cuota_demanda: float) -> float:
    """Captura potencial del punto: TAM × (Demanda_j / Σ_i D_i).

    :param p_cuota_demanda: fracción de la demanda que Huff asigna al punto (0–1).
    """
    if not 0 <= p_cuota_demanda <= 1:
        raise ValueError("la cuota de demanda debe estar entre 0 y 1")
    return tam_valor * p_cuota_demanda
