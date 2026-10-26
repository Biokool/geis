"""Negocios ancla y su efecto en la atractividad de Huff (§3.12.3, ANC-01).

Un negocio ancla genera viajes recurrentes a su entorno (farmacias de
descuento con consultorio, supermercados, conveniencia, bancos, plazas,
hospitales, escuelas grandes, gasolineras). GEIS lo formaliza como
multiplicador de la atractividad del punto candidato:

    A' = A × (1 + Σ_a w_a)   para las anclas a dentro de su radio de efecto.

Detección: por clase SCIAN y/o por palabra clave en el nombre DENUE
(p. ej. una farmacia de descuento registrada con clase genérica).
"""
from __future__ import annotations

import re

#: Catálogo de anclas: tipo, peso w, radio de efecto (m), detección.
ANCHOR_WEIGHTS: list[dict] = [
    {"tipo": "farmacia_descuento", "etiqueta": "Farmacia de descuento",
     "w": 0.30, "radio_m": 400,
     "scian": ["464111"],
     "nombre_kw": ["farmacias similares", "farmacia similares", "similares",
                   "farmacias del ahorro", "del ahorro", "farmacia guadalajara",
                   "benavides", "san pablo"]},
    {"tipo": "supermercado", "etiqueta": "Supermercado",
     "w": 0.40, "radio_m": 600,
     "scian": ["462111", "462112"],
     "nombre_kw": ["walmart", "soriana", "chedraui", "bodega aurrera",
                   "aurrera", "la comer", "heb", "h-e-b", "costco",
                   "sams club", "sam's club", "superama", "fresko"]},
    {"tipo": "conveniencia", "etiqueta": "Tienda de conveniencia",
     "w": 0.20, "radio_m": 300,
     "scian": ["462112"],
     "nombre_kw": ["oxxo", "7-eleven", "7 eleven", "circle k", "extra"]},
    {"tipo": "banco", "etiqueta": "Banco",
     "w": 0.20, "radio_m": 400,
     "scian": ["522110", "522120", "522210"],
     "nombre_kw": ["banorte", "bbva", "banamex", "citibanamex", "santander",
                   "hsbc", "scotiabank", "banregio", "banco azteca", "inbursa"]},
    {"tipo": "plaza", "etiqueta": "Plaza / centro comercial",
     "w": 0.50, "radio_m": 800,
     "scian": ["531110", "531119"],
     "nombre_kw": ["plaza", "centro comercial", "mall", "galerias",
                   "galerías", "power center"]},
    {"tipo": "hospital", "etiqueta": "Hospital",
     "w": 0.35, "radio_m": 600,
     "scian": ["622111", "622112", "622311"],
     "nombre_kw": ["hospital", "clinica de especialidades", "clínica de especialidades"]},
    {"tipo": "escuela_grande", "etiqueta": "Escuela grande / universidad",
     "w": 0.25, "radio_m": 500,
     "scian": ["611311", "611312", "611171"],
     "nombre_kw": ["universidad", "instituto tecnologico", "tecnologico",
                   "preparatoria", "unam", "ipn", "itesm", "tec de monterrey"]},
    {"tipo": "gasolinera", "etiqueta": "Gasolinera",
     "w": 0.15, "radio_m": 300,
     "scian": ["468411"],
     "nombre_kw": ["pemex", "gasolinera", "gasolineras", "gasolina", "bp",
                   "shell", "mobil", "g500", "oxxo gas"]},
]


def _norm(texto: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _coincide_kw(nombre_n: str, kw: str) -> bool:
    """Palabra/frase completa (evita que «bp» case con «subproductos»)."""
    kw_n = _norm(kw).strip()
    if not kw_n:
        return False
    patron = r"(?<![a-z0-9])" + re.escape(kw_n) + r"(?![a-z0-9])"
    return re.search(patron, nombre_n) is not None


def tipo_ancla(nombre: str | None, scian: str | None) -> dict | None:
    """Entrada del catálogo si el establecimiento es un ancla, o None.

    La coincidencia por nombre tiene prioridad (identifica el formato
    concreto: cadena/ancla) sobre la coincidencia solo por SCIAN.
    """
    nombre_n = _norm(nombre or "")
    for entrada in ANCHOR_WEIGHTS:
        if any(_coincide_kw(nombre_n, kw) for kw in entrada["nombre_kw"]):
            return entrada
    if scian:
        for entrada in ANCHOR_WEIGHTS:
            if str(scian) in entrada["scian"]:
                return entrada
    return None


def detectar_anclas(establecimientos) -> list[dict]:
    """Filtra establecimientos ancla dentro de su radio de efecto.

    Cada establecimiento: dict u objeto con ``nombre``, ``scian_code`` (o
    ``scian``) y ``distancia_m``. Devuelve [{nombre, tipo, etiqueta, w,
    radio_m, distancia_m}] ordenado por distancia.
    """
    anclas: list[dict] = []
    for est in establecimientos:
        if isinstance(est, dict):
            nombre = est.get("nombre")
            scian = est.get("scian_code") or est.get("scian")
            dist = est.get("distancia_m")
        else:
            nombre = getattr(est, "nombre", None)
            scian = getattr(est, "scian_code", None) or getattr(est, "scian", None)
            dist = getattr(est, "distancia_m", None)
        entrada = tipo_ancla(nombre, str(scian) if scian else None)
        if entrada is None:
            continue
        if dist is not None and float(dist) > entrada["radio_m"]:
            continue
        anclas.append({
            "nombre": nombre,
            "tipo": entrada["tipo"],
            "etiqueta": entrada["etiqueta"],
            "w": entrada["w"],
            "radio_m": entrada["radio_m"],
            "distancia_m": round(float(dist), 1) if dist is not None else None,
        })
    anclas.sort(key=lambda a: a["distancia_m"] if a["distancia_m"] is not None else 1e18)
    return anclas


def multiplicador(anclas: list[dict]) -> float:
    """Multiplicador de atractividad: 1 + Σ w_a (§3.12.3)."""
    return 1.0 + sum(float(a.get("w", 0.0)) for a in anclas)


def aplicar_efecto_ancla(atractivo: float, anclas: list[dict]) -> float:
    """A' = A × (1 + Σ w_a). Sin anclas, devuelve A intacto."""
    return atractivo * multiplicador(anclas)
