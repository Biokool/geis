"""Índice de Demanda Térmica (IDT) — SRS §3.4.

Índice 0–100 que estima la propensión de una nave/planta industrial a
requerir climatización, aislamiento térmico o eficiencia energética.
Motor del Caso de uso 1 (prospección B2B).
"""
from __future__ import annotations

#: Pesos por defecto (w1..w4): estrato, intensidad SCIAN, clima, antigüedad.
PESOS_DEFAULT: tuple[float, float, float, float] = (0.35, 0.30, 0.20, 0.15)

#: Estrato de personal (ordinal 1–7) → E_estrato normalizado 0–1.
#: Proxy de superficie climatizable.
ESTRATO_ESCALA: dict[int, float] = {
    1: 0.10,  # 0 a 5
    2: 0.25,  # 6 a 10
    3: 0.40,  # 11 a 30
    4: 0.55,  # 31 a 50
    5: 0.70,  # 51 a 100
    6: 0.85,  # 101 a 250
    7: 1.00,  # 251 y más
}


def e_estrato(estrato_ordinal: int) -> float:
    """Normaliza el estrato de personal (1–7) a 0–1."""
    try:
        return ESTRATO_ESCALA[estrato_ordinal]
    except KeyError:
        raise ValueError(f"estrato_ordinal debe estar entre 1 y 7, recibido {estrato_ordinal}")


def idt(
    estrato_ord: int,
    intensidad_scian: float,
    clima: float,
    antiguedad: float | None,
    pesos: tuple[float, float, float, float] = PESOS_DEFAULT,
) -> dict:
    """IDT = 100 × (w1·E_estrato + w2·I_scian + w3·T_clima + w4·A_antigüedad).

    Devuelve un dict con el índice y el desglose por componente, marcando
    los datos faltantes (IDT-02: el IDT muestra su incertidumbre).

    :param estrato_ord: estrato de personal ordinal (1–7).
    :param intensidad_scian: intensidad térmica de la clase SCIAN (0–1).
    :param clima: demanda climática del municipio normalizada (0–1).
    :param antiguedad: antigüedad estimada normalizada (0–1); si es None se
        usa 0.5 neutro con bandera ``dato_no_disponible``.
    :param pesos: (w1, w2, w3, w4); deben sumar 1.
    """
    if abs(sum(pesos) - 1.0) > 1e-9:
        raise ValueError("los pesos deben sumar 1")
    for nombre, valor in (("intensidad_scian", intensidad_scian), ("clima", clima)):
        if not 0 <= valor <= 1:
            raise ValueError(f"{nombre} debe estar entre 0 y 1")

    faltantes: list[str] = []
    if antiguedad is None:
        antiguedad = 0.5
        faltantes.append("antiguedad")
    elif not 0 <= antiguedad <= 1:
        raise ValueError("antiguedad debe estar entre 0 y 1")

    w1, w2, w3, w4 = pesos
    e = e_estrato(estrato_ord)
    componentes = {
        "estrato": w1 * e,
        "intensidad_scian": w2 * intensidad_scian,
        "clima": w3 * clima,
        "antiguedad": w4 * antiguedad,
    }
    valor = 100.0 * sum(componentes.values())
    return {
        "idt": round(valor, 2),
        "componentes": {k: round(v * 100, 2) for k, v in componentes.items()},
        "entradas": {
            "e_estrato": e,
            "intensidad_scian": intensidad_scian,
            "clima": clima,
            "antiguedad": antiguedad,
        },
        "pesos": list(pesos),
        "datos_faltantes": faltantes,
    }
