"""Modelo de gravedad de Huff (1964) — SRS §3.2.

Estima la probabilidad de que un consumidor ubicado en i visite el
establecimiento j, en función del atractivo de j y la fricción de la
distancia. GEIS lo usa para repartir la demanda del territorio entre el
punto candidato y sus competidores.
"""
from __future__ import annotations

from collections.abc import Sequence


def p_ij(
    atractivo_j: float,
    dist_j: float,
    competidores: Sequence[tuple[float, float]],
    alpha: float = 1.0,
    lambda_: float = 2.0,
) -> float:
    """Probabilidad de Huff de que el consumidor en i elija el punto j.

    P_ij = (A_j^α / D_ij^λ) / Σ_k (A_k^α / D_ik^λ)

    :param atractivo_j: atractivo del punto candidato (0–1 compuesto).
    :param dist_j: distancia (o tiempo) i → j, en las mismas unidades que
        las de los competidores y > 0.
    :param competidores: lista de (atractivo_k, distancia_ik) de los
        competidores del giro en el territorio.
    :param alpha: elasticidad del atractivo (típico 1.0).
    :param lambda_: fricción de la distancia (típico 2.0; conveniencia alto,
        destino bajo). Se nombra ``lambda_`` porque ``lambda`` es reservada.
    """
    if dist_j <= 0:
        raise ValueError("dist_j debe ser > 0")
    if atractivo_j < 0:
        raise ValueError("el atractivo no puede ser negativo")

    def _utilidad(atractivo: float, dist: float) -> float:
        if dist <= 0:
            raise ValueError("toda distancia debe ser > 0")
        return (atractivo**alpha) / (dist**lambda_)

    numerador = _utilidad(atractivo_j, dist_j)
    denominador = numerador + sum(_utilidad(a, d) for a, d in competidores)
    if denominador == 0:
        return 0.0
    return numerador / denominador


def p_ij_rango(
    atractivo_j: float,
    dist_j: float,
    competidores: Sequence[tuple[float, float]],
    alpha: float = 1.0,
    lambda_: float = 2.0,
    delta: float = 0.5,
) -> tuple[float, float, float]:
    """Rango de sensibilidad de P_ij con λ ± delta (HUFF-03).

    Devuelve ``(p_min, p_punto, p_max)`` para comunicar sensibilidad en
    lugar de un punto exacto.
    """
    p_punto = p_ij(atractivo_j, dist_j, competidores, alpha, lambda_)
    p_bajo = p_ij(atractivo_j, dist_j, competidores, alpha, lambda_ + delta)
    p_alto = p_ij(atractivo_j, dist_j, competidores, alpha, max(lambda_ - delta, 0.1))
    return (min(p_bajo, p_alto), p_punto, max(p_bajo, p_alto))


def demanda_capturada(p_por_zona: Sequence[tuple[float, float]]) -> float:
    """Demanda capturada estimada: Σ_i (P_ij × D_i) (§3.2)."""
    return sum(p * d for p, d in p_por_zona)
