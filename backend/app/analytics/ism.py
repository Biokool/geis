"""Índice de Saturación de Mercado (ISM) — SRS §3.1.

El ISM mide cuánta **demanda** existe por cada unidad de **oferta** en un
territorio, para un giro dado. Es el indicador central de la lectura
"océano azul / océano rojo".
"""
from __future__ import annotations


def ism(demanda: float, oferta: float) -> float:
    """Calcula el ISM = D / (O + 1).

    El +1 es un suavizado de Laplace: evita la división entre cero cuando
    no hay competencia registrada y estabiliza el índice en territorios con
    poca oferta (ISM-03: se recalcula por anillo, no se promedian anillos).
    """
    if demanda < 0:
        raise ValueError("la demanda (D) no puede ser negativa")
    if oferta < 0:
        raise ValueError("la oferta (O) no puede ser negativa")
    return demanda / (oferta + 1.0)


#: Bandas de lectura del ISM según el benchmark del territorio.
BANDAS = (
    "oceano_azul",   # ISM >= P90: territorio desatendido
    "equilibrado",   # P50 <= ISM < P90: entrada viable con diferenciación
    "competido",     # P10 <= ISM < P50: entrada solo con ventaja clara
    "oceano_rojo",   # ISM < P10: saturado
)


def ism_band(ism_value: float, p50: float, p90: float, p10: float | None = None) -> str:
    """Clasifica un ISM contra los percentiles del benchmark.

    Con ``p10`` se devuelven las 4 bandas del SRS; sin ``p10`` se colapsa a
    3 bandas (``competido`` y ``oceano_rojo`` se fusionan en ``oceano_rojo``).
    """
    if ism_value >= p90:
        return "oceano_azul"
    if ism_value >= p50:
        return "equilibrado"
    if p10 is not None and ism_value >= p10:
        return "competido"
    return "oceano_rojo"


def ism_descripcion(banda: str) -> str:
    """Texto legible de la banda del ISM."""
    return {
        "oceano_azul": "Océano azul: mucha demanda por competidor (territorio desatendido)",
        "equilibrado": "Mercado equilibrado: entrada viable con diferenciación",
        "competido": "Mercado competido: entrada solo con ventaja clara",
        "oceano_rojo": "Océano rojo: territorio saturado",
    }[banda]
