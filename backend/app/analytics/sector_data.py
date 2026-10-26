"""Catálogo sectorial por giro — fichas de los 15 giros frecuentes (Anexo B.4).

Datos en código (editables sin BD): cada ficha trae las clases SCIAN del
giro, un texto editorial breve para la § «Perfil del cliente», los supuestos
TAM (gasto promedio mensual por cliente objetivo, factor NSE y penetración),
la plantilla de punto de equilibrio (§3.12.2: costos fijos típicos y margen
de contribución) y los datos sectoriales que muestra el reporte (ticket
promedio, hora pico, % de ventas por delivery, productos top y fuente).

Los valores son supuestos de arranque documentados como tales («supuesto
editable»): el análisis los usa solo cuando el giro coincide con una ficha;
para giros sin ficha se conserva el default histórico de ``analysis.py``.
Los overrides del request siempre ganan sobre la ficha.
"""
from __future__ import annotations

import unicodedata


def _norm(texto: str | None) -> str:
    """Minúsculas sin acentos, para comparar giros en texto libre."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _ficha(
    clave: str, nombre: str, scian: list[str], editorial: str,
    gasto_mensual: float, f_nse: float, f_pen: float,
    costos: dict[str, float], margen: float,
    ticket: float, hora_pico: str, delivery_pct: float | None,
    top_productos: list[str], fuente: str, delivery: bool,
) -> dict:
    # «insumos» es costo variable: se separa para no contarlo dos veces (el
    # margen de contribución ya lo excluye). Los fijos son el resto.
    variables = {"insumos": costos.get("insumos", 0.0)}
    fijos = {k: v for k, v in costos.items() if k != "insumos"}
    return {
        "clave": clave,
        "nombre": nombre,
        "scian": scian,
        "editorial": editorial,
        "tam_supuestos": {
            "gasto_promedio_mensual": gasto_mensual,
            "gasto_pc_mxn_anual": round(gasto_mensual * 12, 2),
            "f_nse": f_nse,
            "f_pen": f_pen,
            "fuente": "catálogo sectorial GEIS (supuesto editable)",
        },
        "break_even": {
            "costos_fijos": fijos,
            "costos_variables": variables,
            "total_costos_fijos": round(sum(fijos.values()), 2),
            "total_costos_variables": round(sum(variables.values()), 2),
            "margen_contribucion": margen,
            "formula": "Ventas_equilibrio = Costos_fijos / margen_contribucion (§3.12.2)",
        },
        "sector": {
            "ticket_promedio": ticket,
            "hora_pico": hora_pico,
            "delivery_pct": delivery_pct,
            "top_productos": top_productos,
            "fuente": fuente,
        },
        "delivery": delivery,
    }


_COSTOS_BASE = {
    "nomina": 18000.0, "renta": 12000.0, "servicios": 3500.0,
    "contador": 1500.0, "impuestos": 2500.0, "insumos": 6000.0,
    "mantenimiento": 1200.0, "imprevistos": 1500.0,
}


def _costos(**ajustes: float) -> dict[str, float]:
    c = dict(_COSTOS_BASE)
    c.update(ajustes)
    return c


#: Fichas por clave normalizada (sin acentos).
FICHAS: dict[str, dict] = {}


def _registrar(aliases: list[str], ficha: dict) -> None:
    for alias in aliases:
        FICHAS[_norm(alias)] = ficha


_registrar(["cafetería", "cafeteria", "café", "cafe"], _ficha(
    "cafeterias", "Cafeterías", ["722515"],
    "El cliente de cafetería busca una pausa de calidad cerca de su rutina: "
    "consume entre semana camino al trabajo o estudio y el fin de semana "
    "como plan social. Valora ambiente, wifi y rapidez en hora pico.",
    200.0, 1.15, 0.45, _costos(), 0.62,
    95.0, "8:00–10:00 y 17:00–19:00", 18.0,
    ["Café americano", "Capuchino", "Pan dulce", "Sándwiches"],
    "Estimación GEIS con referencias PROFECO/Parrot (supuesto editable)", True,
))
_registrar(["sushi", "comida japonesa"], _ficha(
    "sushi", "Sushi", ["722511", "722514"],
    "El cliente de sushi compra por antojo y ocasión: parejas y grupos "
    "pequeños, con peso fuerte del delivery nocturno y de fin de semana.",
    320.0, 1.20, 0.30, _costos(nomina=21000.0, insumos=9000.0), 0.58,
    260.0, "19:00–22:00", 45.0,
    ["Rollos especiales", "Nigiri", "Ramen", "Yakimeshi"],
    "Estimación GEIS con referencias Rappi/Parrot (supuesto editable)", True,
))
_registrar(["tintorería", "tintoreria"], _ficha(
    "tintoreria", "Tintorería", ["812320"],
    "El cliente de tintorería es recurrente y de proximidad: deja prendas "
    "de trabajo y ocasión especial; la confianza y el tiempo de entrega "
    "mandan sobre el precio.",
    260.0, 1.10, 0.35, _costos(nomina=12000.0, renta=8000.0, insumos=3500.0), 0.60,
    180.0, "9:00–11:00 y 18:00–20:00", None,
    ["Trajes", "Vestidos", "Camisas", "Edredones"],
    "Estimación GEIS (supuesto editable)", False,
))
_registrar(["tortillería", "tortilleria"], _ficha(
    "tortilleria", "Tortillería", ["311830"],
    "Negocio de frecuencia diaria y ticket bajo: el cliente vive a pocas "
    "cuadras y compra para la comida del día; la ubicación sobre flujo "
    "peatonal es decisiva.",
    150.0, 0.95, 0.70, _costos(nomina=10000.0, renta=6000.0, insumos=8000.0), 0.45,
    28.0, "12:00–15:00", None,
    ["Tortilla de maíz", "Masa", "Totopos", "Salsas"],
    "Estimación GEIS con referencias PROFECO (supuesto editable)", False,
))
_registrar(["carnicería", "carniceria", "carnicero"], _ficha(
    "carniceria", "Carnicería", ["461160"],
    "El cliente de carnicería compra para la comida familiar de la semana; "
    "compara frescura y precio por kilo y premia la confianza del carnicero.",
    420.0, 1.00, 0.50, _costos(nomina=14000.0, insumos=12000.0), 0.38,
    210.0, "10:00–13:00", 8.0,
    ["Bistec", "Molida", "Pollo entero", "Cerdo"],
    "Estimación GEIS con referencias PROFECO (supuesto editable)", True,
))
_registrar(["lavandería", "lavanderia"], _ficha(
    "lavanderia", "Lavandería", ["812310"],
    "El cliente de lavandería vive cerca, muchas veces sin lavadora en "
    "casa o con poco tiempo; compra por kilo y repite cada semana.",
    220.0, 0.95, 0.50, _costos(nomina=9000.0, renta=7000.0, servicios=4500.0), 0.65,
    120.0, "10:00–13:00 (fin de semana)", None,
    ["Lavado por kilo", "Planchado", "Edredones", "Autoservicio"],
    "Estimación GEIS (supuesto editable)", False,
))
_registrar(["barbería", "barberia", "barber shop"], _ficha(
    "barberia", "Barbería", ["812110"],
    "El cliente de barbería es leal a su barbero y compra cada 2–3 semanas; "
    "la experiencia, la cita puntual y la ubicación en flujo masculino "
    "joven pesan más que el precio.",
    280.0, 1.05, 0.55, _costos(nomina=12000.0, renta=7000.0, insumos=2000.0), 0.70,
    180.0, "17:00–20:00", None,
    ["Corte clásico", "Fade", "Arreglo de barba", "Diseños"],
    "Estimación GEIS (supuesto editable)", False,
))
_registrar(["pizzería", "pizzeria", "pizza"], _ficha(
    "pizzeria", "Pizzería", ["722513"],
    "La pizza es compra familiar y de grupo, concentrada en noches y fines "
    "de semana; el delivery es el canal dominante y el radio de reparto "
    "define el mercado real.",
    300.0, 1.05, 0.40, _costos(nomina=16000.0, insumos=10000.0), 0.60,
    240.0, "19:00–22:00", 55.0,
    ["Pizza familiar", "Pizza mediana", "Alitas", "Refrescos"],
    "Estimación GEIS con referencias Rappi/Parrot (supuesto editable)", True,
))
_registrar(["matcha", "té matcha", "te matcha"], _ficha(
    "matcha", "Matcha", ["722515"],
    "El cliente de matcha es joven, urbano y de ticket medio-alto: compra "
    "por tendencia, estética del local y redes sociales; concentra su "
    "consumo en zonas de oficinas, universidades y vida de barrio premium.",
    240.0, 1.25, 0.30, _costos(insumos=5000.0), 0.65,
    110.0, "11:00–14:00 y 17:00–19:00", 15.0,
    ["Matcha latte", "Matcha ceremonial", "Postres de matcha", "Bebidas frías"],
    "Estimación GEIS (supuesto editable)", True,
))
_registrar(["food truck", "foodtruck", "camión de comida"], _ficha(
    "food_truck", "Food truck", ["722330"],
    "El food truck vende donde está el flujo: oficinas, universidades, "
    "eventos y vida nocturna. Su mercado no es un radio fijo sino una "
    "agenda de puntos; el análisis aplica al punto base de operación.",
    180.0, 1.05, 0.35, _costos(nomina=10000.0, renta=3000.0, insumos=9000.0), 0.55,
    130.0, "13:00–15:00 y 19:00–22:00", 20.0,
    ["Platillo insignia", "Combos", "Bebidas", "Postres"],
    "Estimación GEIS (supuesto editable)", True,
))
_registrar(["pollo asado", "pollo rostizado", "rosticería", "rosticeria"], _ficha(
    "pollo_asado", "Pollo asado", ["722511"],
    "Compra familiar de fin de semana y comida del día: el cliente busca "
    "precio por paquete completo y rapidez; el aroma y la visibilidad "
    "desde la vialidad venden.",
    260.0, 0.95, 0.45, _costos(nomina=13000.0, insumos=11000.0), 0.42,
    190.0, "13:00–15:30", 25.0,
    ["Pollo entero", "Medio pollo", "Paquetes familiares", "Complementos"],
    "Estimación GEIS con referencias PROFECO (supuesto editable)", True,
))
_registrar(["farmacia", "farmacias"], _ficha(
    "farmacias", "Farmacias", ["464111"],
    "La farmacia es compra de necesidad y urgencia, muy de proximidad; "
    "las cadenas con consultorio anexo actúan además como negocio ancla "
    "que genera viajes recurrentes a la zona.",
    350.0, 1.05, 0.50, _costos(nomina=20000.0, renta=15000.0, insumos=15000.0), 0.35,
    160.0, "9:00–12:00 y 18:00–21:00", 30.0,
    ["Medicamentos OTC", "Consulta anexa", "Cuidado personal", "Vitaminas"],
    "Estimación GEIS (supuesto editable)", True,
))
_registrar(["laboratorio clínico", "laboratorios clínicos", "laboratorio clinico", "laboratorios"], _ficha(
    "laboratorios", "Laboratorios clínicos", ["621511"],
    "El cliente de laboratorio llega por referencia médica y en ayunas a "
    "primera hora; compite por precio transparente, rapidez de resultados "
    "en línea y cercanía a consultorios y hospitales.",
    380.0, 1.10, 0.35, _costos(nomina=22000.0, renta=14000.0, insumos=8000.0), 0.55,
    420.0, "7:00–10:00", None,
    ["Química sanguínea", "Biometría hemática", "Perfiles", "Pruebas especiales"],
    "Estimación GEIS (supuesto editable)", False,
))
_registrar(["consultorio dental", "dentista", "clínica dental", "clinica dental", "dental"], _ficha(
    "dental", "Consultorio dental", ["621211"],
    "El paciente dental elige por confianza, recomendación y facilidades "
    "de pago; la primera visita suele venir de la cercanía a casa o "
    "trabajo y la recurrencia es de largo plazo.",
    450.0, 1.15, 0.40, _costos(nomina=18000.0, renta=11000.0, insumos=6000.0), 0.60,
    650.0, "10:00–13:00 y 17:00–20:00", None,
    ["Limpieza", "Resinas", "Ortodoncia", "Implantes"],
    "Estimación GEIS (supuesto editable)", False,
))
_registrar(["franquicia", "franquicias"], _ficha(
    "franquicias", "Franquicias", ["722511"],
    "El franquiciatario compra un modelo probado: evalúa territorio con "
    "la misma vara que la marca (población objetivo, NSE, competencia de "
    "la misma cadena) y necesita el punto de equilibrio contra la renta "
    "y las regalías desde el día uno.",
    300.0, 1.10, 0.40, _costos(nomina=20000.0, renta=18000.0, insumos=10000.0), 0.58,
    180.0, "Variable según formato", 30.0,
    ["Según formato de la marca"],
    "Estimación GEIS (supuesto editable)", True,
))


def buscar_ficha(giro: str | None) -> dict | None:
    """Ficha sectorial del giro en texto libre, o None si no hay ficha.

    Coincidencia por alias exacto normalizado o por contención (el alias
    aparece dentro del texto del giro, p. ej. «cafetería de especialidad»).
    """
    clave = _norm(giro)
    if not clave:
        return None
    if clave in FICHAS:
        return FICHAS[clave]
    # Alias más largo primero: gana la coincidencia más específica.
    for alias in sorted(FICHAS, key=len, reverse=True):
        if alias and alias in clave:
            return FICHAS[alias]
    return None


def ventas_equilibrio(ficha: dict) -> float:
    """Ventas mensuales de equilibrio de la ficha (§3.12.2)."""
    be = ficha["break_even"]
    margen = be["margen_contribucion"] or 0.0
    if margen <= 0:
        return 0.0
    return round(be["total_costos_fijos"] / margen, 2)
