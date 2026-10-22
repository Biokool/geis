"""Score de cuenta B2B (account scoring) — SRS §3.5.

Score 0–100 que prioriza cuentas para la fuerza de ventas, combinando
necesidad (IDT), tamaño, accesibilidad y eficiencia comercial.
"""
from __future__ import annotations

#: Pesos por defecto por componente (SC-02: configurables por vertical).
PESOS_DEFAULT: dict[str, float] = {
    "idt": 0.40,          # necesidad térmica (IDT/100)
    "tamano": 0.20,       # tamaño relativo (estrato normalizado)
    "accesibilidad": 0.15,  # 1 − min(dist_a_corredor_km/10, 1)
    "densidad": 0.15,     # cuentas elegibles en 5 km normalizadas
    "contacto": 0.10,     # completitud de contacto
}


def b2b_score(
    componentes: dict[str, float | None],
    pesos: dict[str, float] | None = None,
) -> dict:
    """Score = 100 × Σ(w_m × x_m) / Σ w_m, solo sobre componentes disponibles.

    :param componentes: dict con las claves de ``PESOS_DEFAULT`` y valores
        0–1 (None = no disponible, se excluye del cálculo).
    :param pesos: pesos por componente; por defecto ``PESOS_DEFAULT``.
    :returns: dict con ``score`` (0–100), ``desglose`` por componente
        (contribución en puntos) y ``componentes_usados``.
    """
    pesos = dict(PESOS_DEFAULT if pesos is None else pesos)
    if any(w < 0 for w in pesos.values()):
        raise ValueError("los pesos no pueden ser negativos")

    usados: dict[str, float] = {}
    for clave, valor in componentes.items():
        if clave not in pesos:
            raise ValueError(f"componente desconocido: {clave!r}")
        if valor is None:
            continue
        if not 0 <= valor <= 1:
            raise ValueError(f"el componente {clave!r} debe estar en 0–1")
        usados[clave] = valor

    if not usados:
        raise ValueError("se requiere al menos un componente disponible")

    suma_pesos = sum(pesos[k] for k in usados)
    if suma_pesos <= 0:
        raise ValueError(
            "la suma de los pesos de los componentes disponibles debe ser > 0"
        )
    contribuciones = {k: 100.0 * pesos[k] * v / suma_pesos for k, v in usados.items()}
    return {
        "score": round(sum(contribuciones.values()), 2),
        "desglose": {k: round(v, 2) for k, v in contribuciones.items()},
        "componentes_usados": sorted(usados),
        "pesos": {k: pesos[k] for k in usados},
    }


def completitud_contacto(telefono: bool, correo: bool, sitio: bool) -> float:
    """Completitud de contacto: 0.33×tel + 0.33×correo + 0.34×sitio (§3.5)."""
    return round(0.33 * float(telefono) + 0.33 * float(correo) + 0.34 * float(sitio), 2)


def accesibilidad_logistica(dist_a_corredor_km: float) -> float:
    """Accesibilidad: 1 − min(dist_km / 10, 1) (§3.5)."""
    if dist_a_corredor_km < 0:
        raise ValueError("la distancia no puede ser negativa")
    return round(1.0 - min(dist_a_corredor_km / 10.0, 1.0), 4)
