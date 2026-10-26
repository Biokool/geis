"""Proxies de movilidad vehicular y peatonal — SRS §3.10.

Sin sensores ni conector de tráfico, GEIS estima rangos transparentes a
partir de la red vial OSM cercana, la población del radio y los
atractores/entorno. Reglas FLU-01: el resultado SIEMPRE lleva
``estimado: true``, se expresa como rango (nunca cifra exacta fingida) y
un nivel 0–100 comparable entre ubicaciones.

Flujo vehicular (proxy, adaptación operativa de §3.10)::

    V_día ≈ Σ_v (flujo_típico_v)   sobre vialidades principales únicas

con flujo típico por jerarquía OSM: trunk 28,000 · primary 18,000 ·
secondary 9,000 vehículos/día, atenuado si la vialidad está lejos
(>1,000 m: ×0.6; >1,500 m: ×0.35). Sin vialidades principales, se cae a
un basal por densidad de población (1.2 vehículos/día por habitante del
radio, tope 6,000).

Flujo peatonal (proxy, fórmula §3.10)::

    P_día ≈ población_500m × 0.15 + empleos_500m × 0.40 + atractores × w_cat

con w_cat = 120 personas/día por atractor cercano y factor_horario = 1.
La población de 500 m se aproxima por área desde la del radio mayor
(supuesto documentado en la salida). El rango es ±30 %.
"""
from __future__ import annotations

#: Flujo típico vehículos/día por jerarquía OSM (conteos de referencia).
FLUJO_POR_TIPO: dict[str, float] = {
    "trunk": 28000.0,
    "primary": 18000.0,
    "secondary": 9000.0,
}

W_ATRACTOR_PEATONAL = 120.0


def _atenuacion(distancia_m: float | None) -> float:
    if distancia_m is None:
        return 1.0
    if distancia_m > 1500:
        return 0.35
    if distancia_m > 1000:
        return 0.6
    return 1.0


def proxy_vehicular(
    vialidades: list[dict],
    poblacion_radio: float = 0.0,
) -> dict:
    """Proxy vehicular: rango de vehículos/día + nivel 0–100 (estimado)."""
    # Vialidades únicas por nombre+tipo para no contar dos veces la misma vía.
    vistas: set[tuple[str, str]] = set()
    total = 0.0
    for v in vialidades or []:
        tipo = str(v.get("tipo") or v.get("highway") or "").lower()
        if tipo not in FLUJO_POR_TIPO:
            continue
        clave = (str(v.get("nombre") or tipo), tipo)
        if clave in vistas:
            continue
        vistas.add(clave)
        total += FLUJO_POR_TIPO[tipo] * _atenuacion(v.get("distancia_m"))
    metodo = ("proxy §3.10: Σ flujo típico por jerarquía OSM atenuado "
              "por distancia (sin sensor ni conector de tráfico)")
    if total <= 0:
        basal = min(float(poblacion_radio or 0) * 1.2, 6000.0)
        if basal <= 0:
            # Sin vialidades ni población no se inventa un rango: se declara.
            return {
                "estimado": True,
                "rango_vehiculos_dia": None,
                "etiqueta": "Sin datos suficientes para estimar flujo vehicular",
                "nivel": None,
                "metodo": "proxy §3.10: sin vialidades principales ni población "
                          "en el radio; no se estima un flujo",
            }
        total = basal
        metodo = ("proxy §3.10: basal por población del radio (sin "
                  "vialidades OSM disponibles); estimación, no conteo")
    bajo = round(total * 0.75)
    alto = round(total * 1.15)
    nivel = int(max(0, min(100, round(total / 450.0))))
    return {
        "estimado": True,
        "rango_vehiculos_dia": [bajo, alto],
        "etiqueta": f"{alto:,} o más vehículos/día".replace(",", ",")
        if total >= 15000 else f"{bajo:,} a {alto:,} vehículos/día",
        "nivel": nivel,
        "metodo": metodo,
    }


def proxy_peatonal(
    poblacion_radio: float = 0.0,
    radio_m: int = 2000,
    pea_ocupada: float = 0.0,
    n_atractores: int = 0,
) -> dict:
    """Proxy peatonal: rango de personas/día + nivel 0–100 (estimado)."""
    # Aproximación por área a 500 m desde el radio de análisis.
    if radio_m and radio_m > 500:
        factor_area = (500.0 / float(radio_m)) ** 2
    else:
        factor_area = 1.0
    pob_500 = float(poblacion_radio or 0) * factor_area
    empleos_500 = float(pea_ocupada or 0) * factor_area
    punto = pob_500 * 0.15 + empleos_500 * 0.40 + float(n_atractores) * W_ATRACTOR_PEATONAL
    bajo = round(punto * 0.7)
    alto = round(punto * 1.3)
    nivel = int(max(0, min(100, round(punto / 90.0))))
    return {
        "estimado": True,
        "rango_personas_dia": [bajo, alto],
        "etiqueta": f"{bajo:,} a {alto:,} personas podrían pasar caminando cerca",
        "nivel": nivel,
        "metodo": "proxy §3.10: población_500m×0.15 + empleos_500m×0.40 + "
                  "atractores×120 (estimación por modelo, no conteo observado)",
        "supuestos": {
            "poblacion_500m_aprox": round(pob_500, 1),
            "empleos_500m_aprox": round(empleos_500, 1),
            "n_atractores": int(n_atractores),
        },
    }


def actividad_economica(pea_ocupada: float | None, poblacion_total: float | None,
                        pob_15_mas: float | None = None) -> dict:
    """Actividad económica de la zona: PEA ocupada y % sobre población 15+."""
    base = pob_15_mas
    pct = None
    if pea_ocupada is not None and base:
        pct = round(100.0 * float(pea_ocupada) / float(base), 1)
    return {
        "pea_ocupada": pea_ocupada,
        "pct_sobre_pob_15_mas": pct,
        "nota": "Personas ocupadas residentes en la zona (Censo), no empleo "
                "generado en la zona.",
    }
