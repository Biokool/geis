"""Score unificado GEIS × Biokool Radar (§5 del blueprint de fusión).

Fusiona los componentes ESPACIALES de GEIS (IDT, tamaño, accesibilidad,
densidad, completitud de contacto) con los CONDUCTUALES de Radar
(temperatura de zona, señales cálidas, engagement de LinkedIn).

Los pesos legacy de Radar (+20 por temperatura, +25 por señal) se
normalizan a la escala 0–100: ya no son sumas aritméticas que pueden
pasar de 100, sino componentes x_m ∈ 0–1 ponderados con w_m.

El cálculo final lo hace ``b2b_score`` de ``app.analytics.scoring``:
Score = 100 × Σ(w_m × x_m) / Σ w_m, solo sobre componentes disponibles.
"""
from __future__ import annotations

import re
from datetime import datetime

from app.analytics.scoring import b2b_score

#: Claves de componentes espaciales (GEIS).
ESPACIALES = ("idt", "tamano", "acceso", "densidad", "contacto")

#: Claves de componentes conductuales (Radar).
CONDUCTUALES = ("temp", "senal", "linkedin")

#: Perfil biokool: pesos del §5 del blueprint (suman 1.0).
PESOS_BIOKOOL: dict[str, float] = {
    "idt": 0.30,       # necesidad térmica (IDT/100)
    "tamano": 0.12,    # estrato normalizado
    "acceso": 0.10,    # accesibilidad logística
    "densidad": 0.08,  # densidad de cuentas (KDE)
    "contacto": 0.05,  # completitud de contacto
    "temp": 0.15,      # 1 si temp_zona > 30 °C (+20 legacy normalizado)
    "senal": 0.15,     # 1 si hay señal manual/cálida (+25 legacy normalizado)
    "linkedin": 0.05,  # engagement cálido reciente
}

#: Perfil genérico: solo componentes espaciales, renormalizados a suma 1.
_SUMA_ESPACIAL = sum(PESOS_BIOKOOL[k] for k in ESPACIALES)
PESOS_GENERICO: dict[str, float] = {
    k: PESOS_BIOKOOL[k] / _SUMA_ESPACIAL for k in ESPACIALES
}

#: Temperatura de zona (°C) que activa el componente térmico.
UMBRAL_TEMP_C = 30.0

#: Giros que, en invierno, inclinan la línea recomendada a 'solar'.
GIROS_SOLAR = ("gasolin", "estacionamiento", "plaza comercial", "comercial")


def _normalizar_componentes(componentes: dict) -> dict[str, float | None]:
    """Normaliza los insumos legacy a x_m ∈ 0–1.

    - ``temp`` / ``temp_zona`` en °C: >30 °C ⇒ x_temp = 1, si no 0.
    - ``senal`` (bool o 0/1): con señal ⇒ x_senal = 1, si no 0.
    - El resto pasa tal cual (None = no disponible, se excluye).
    """
    out: dict[str, float | None] = {}
    for clave, valor in componentes.items():
        if valor is None:
            continue
        if clave in ("temp", "temp_zona"):
            out["temp"] = 1.0 if float(valor) > UMBRAL_TEMP_C else 0.0
        elif clave == "senal":
            out["senal"] = 1.0 if valor else 0.0
        elif clave in ESPACIALES or clave in CONDUCTUALES:
            out[clave] = float(valor)
        # Claves desconocidas se ignoran (no rompen el cálculo).
    return out


def score_unificado(
    componentes: dict,
    vertical: str = "biokool",
) -> dict:
    """Calcula el score unificado 0–100 para un lead.

    :param componentes: dict con componentes espaciales (idt, tamano,
        acceso, densidad, contacto) y conductuales. Acepta insumos legacy:
        ``temp``/``temp_zona`` en °C y ``senal`` como booleano. Los None
        se excluyen del cálculo.
    :param vertical: 'biokool' (todos los componentes) o 'generico'
        (solo espaciales; los conductuales se ignoran).
    :returns: lo mismo que ``b2b_score`` más ``vertical`` y los valores
        normalizados ``x`` usados.
    """
    normalizados = _normalizar_componentes(componentes)
    if vertical == "generico":
        pesos = PESOS_GENERICO
        normalizados = {k: v for k, v in normalizados.items() if k in pesos}
    elif vertical == "biokool":
        pesos = PESOS_BIOKOOL
    else:
        raise ValueError(
            f"vertical desconocida: {vertical!r} (usa 'biokool' o 'generico')"
        )

    # Integración con el perfil de empresa (módulo company): si hay un
    # perfil activo cuyo vertical coincide con el pedido, sus
    # scoring_weights mandan. Sin perfil, el comportamiento es el de
    # siempre (import lazy para evitar el ciclo company → analytics).
    try:
        from app.company.store import resolve_pesos

        override = resolve_pesos(vertical)
    except Exception:
        override = None
    if override:
        pesos = override
        if vertical == "generico":
            normalizados = {k: v for k, v in normalizados.items() if k in pesos}

    resultado = b2b_score(normalizados, pesos)
    resultado["vertical"] = vertical
    resultado["x"] = normalizados
    return resultado


def _productos_perfil_activo() -> list[str]:
    """Nombres de producto del perfil activo (silencioso si no hay)."""
    try:
        from app.company.store import get_active_config

        cfg = get_active_config()
        return [t["producto"] for t in (cfg or {}).get("tam_defaults", [])]
    except Exception:
        return []


def linea_recomendada(
    mes: int,
    giro: str | None = None,
    productos_perfil: list[str] | None = None,
) -> str:
    """Línea de producto recomendada por mes y giro (regla de negocio v1).

    - feb–jun (mes 2–6) → 'koolkat' (temporada de calor).
    - oct–feb (mes 10,11,12,1,2) + giro de gasolinera/estacionamiento/
      comercial → 'solar' (invierno, instalaciones al aire libre).
    - resto → 'evaporativa'.
    - Además: si el giro menciona un producto del perfil de empresa
      activo (o de ``productos_perfil``), se devuelve ese nombre de
      producto tal cual.

    Cubre los 12 meses sin huecos; ``mes`` fuera de 1–12 lanza ValueError.
    """
    if not 1 <= mes <= 12:
        raise ValueError(f"mes debe estar entre 1 y 12, recibido {mes}")
    productos = productos_perfil if productos_perfil is not None else _productos_perfil_activo()
    if productos and giro:
        g = (giro or "").lower().strip()
        for p in productos:
            pl = str(p).lower().strip()
            if not pl:
                continue
            if pl in g or (len(g) >= 4 and g in pl):
                return str(p)
    if 2 <= mes <= 6:
        return "koolkat"
    if mes in (10, 11, 12, 1, 2):
        giro_lc = (giro or "").lower()
        if any(pista in giro_lc for pista in GIROS_SOLAR):
            return "solar"
    return "evaporativa"


#: Patrones de giro para afinar los argumentos del plan de contacto.
_GIRO_INDUSTRIAL = re.compile(r"industr|nave|log[ií]st|manufact|f[aá]brica|taller|almac")
_GIRO_HOSPITALIDAD = re.compile(r"hotel|restaur|oficina|escuela|cl[ií]nica|hospital")

_MOTIVOS_LINEA = {
    "koolkat": (
        "Estamos en temporada de calor (feb–jun): el control térmico de naves "
        "y locales es la necesidad dominante."
    ),
    "solar": (
        "Temporada de invierno + giro al aire libre: los paneles solares recortan "
        "el recibo de luz justo cuando el consumo de climatización cambia."
    ),
    "evaporativa": (
        "Fuera de la temporada pico de calor: la bioclimatización evaporativa "
        "vende confort con bajo consumo energético todo el año."
    ),
}

_NOMBRES_LINEA = {
    "koolkat": "Koolkat · control térmico",
    "solar": "Solar · paneles fotovoltaicos",
    "evaporativa": "Evaporativa · bioclimatización",
}


def sugerir_plan_contacto(
    giro: str | None,
    temp_c: float | None = None,
    mes: int | None = None,
) -> dict:
    """Plan de contacto sugerido — §14 del reporte (§7 del blueprint de fusión).

    Devuelve ``linea`` (vía :func:`linea_recomendada`), ``motivo_linea``,
    ``argumentos`` afinados por tipo de giro y ``momento`` según la
    temperatura de la zona. Si ``giro`` es None se declara
    ``estado: "dato no disponible"`` en lugar de inventar argumentos.
    """
    if mes is None:
        mes = datetime.now().month
    if not giro:
        return {
            "estado": "dato no disponible",
            "nota": "Sin giro no se puede sugerir línea ni argumentos de contacto.",
            "linea": None,
            "linea_nombre": None,
            "motivo_linea": None,
            "argumentos": [],
            "momento": None,
            "temp_c": temp_c,
        }

    linea = linea_recomendada(mes, giro)
    g = giro.lower()
    es_industrial = bool(_GIRO_INDUSTRIAL.search(g))
    es_hospitalidad = bool(_GIRO_HOSPITALIDAD.search(g))

    argumentos: list[str] = []
    if linea == "koolkat":
        argumentos.append(
            "El calor baja la productividad del personal y pone en riesgo "
            "mercancía sensible a temperatura."
        )
        argumentos.append(
            "Koolkat climatiza grandes volúmenes con una fracción del costo "
            "del aire acondicionado tradicional."
        )
        if es_industrial:
            argumentos.append(
                f"En un giro como «{giro}», el control térmico de la nave protege "
                "tanto a la plantilla como al inventario."
            )
    elif linea == "solar":
        argumentos.append(
            "Los espacios al aire libre consumen mucha energía en iluminación y "
            "bombeo: el sol que los calienta puede pagar su recibo."
        )
        argumentos.append(
            "Paneles solares = gasto operativo predecible por 25 años y "
            "deducción fiscal del activo."
        )
        argumentos.append(
            f"Para «{giro}», la marquesina solar además da sombra a clientes y "
            "vehículos: doble beneficio visible."
        )
    elif linea == "evaporativa":
        argumentos.append(
            "La bioclimatización evaporativa renueva el aire (salud) en vez de "
            "recircularlo, con consumos muy inferiores al minisplit."
        )
        argumentos.append(
            "Ideal para espacios semi-abiertos donde el aire acondicionado no funciona."
        )
        if es_hospitalidad:
            argumentos.append(
                f"En «{giro}», el confort térmico de clientes se nota en reseñas "
                "y permanencia."
            )
        if es_industrial:
            argumentos.append(
                f"En «{giro}», baja la sensación térmica de la nave sin cerrar "
                "puertas ni detener la operación."
            )
    else:
        # Línea = nombre de producto del perfil de empresa (matcheo por
        # giro); argumentos genéricos pero anclados al producto.
        argumentos.append(
            f"Producto «{linea}» del catálogo de la empresa: el giro del "
            f"lead («{giro}») encaja directamente con esta línea."
        )
        argumentos.append(
            "Enfoca el pitch en el producto concreto que el lead ya usa o "
            "necesita, con el vocabulario del perfil de empresa."
        )
        if es_hospitalidad:
            argumentos.append(
                f"En «{giro}», el confort de clientes se nota en reseñas "
                "y permanencia."
            )
        if es_industrial:
            argumentos.append(
                f"En «{giro}», protege tanto a la plantilla como a la "
                "operación."
            )
    argumentos.append(
        "Oferta de arranque: diagnóstico térmico gratuito de la zona con el "
        "mapa de temperatura del módulo Radar."
    )

    if temp_c is None:
        momento = (
            "Sin dato de temperatura en vivo: consulta el pronóstico y agenda la "
            "visita en el día más caluroso de la semana; el calor hace la mitad "
            "del pitch."
        )
    elif temp_c >= 32:
        momento = (
            "Contacto inmediato: hay ola de calor en la zona. Llama hoy y visita "
            "entre 12:00 y 16:00 para que sientan el problema."
        )
    elif temp_c >= 30:
        momento = (
            "Ventana caliente: agenda la visita en el pico de calor del día "
            "(12:00–16:00); el contraste térmico vende solo."
        )
    elif temp_c >= 25:
        momento = (
            "Calor moderado: visita a mediodía y enfoca el argumento en "
            "productividad del personal, no solo en confort."
        )
    else:
        momento = (
            "El calor no aprieta hoy: el pitch debe ir por ahorro de energía y "
            "ROI, no por urgencia térmica. Agenda seguimiento en temporada de calor."
        )

    return {
        "estado": "ok",
        "linea": linea,
        # La línea puede ser un nombre de producto del perfil (no solo las
        # 3 líneas Biokool): .get() con fallback honesto en vez de KeyError.
        "linea_nombre": _NOMBRES_LINEA.get(linea, linea),
        "motivo_linea": _MOTIVOS_LINEA.get(
            linea,
            f"Línea «{linea}» del catálogo de la empresa (ver perfil activo).",
        ),
        "argumentos": argumentos,
        "momento": momento,
        "temp_c": temp_c,
    }
