"""Catálogo de las 9 categorías del entorno comercial (reporte Sabueso §7b/§8).

Módulo compartido y puro: clasifica un código SCIAN (6 dígitos, SCIAN 2023)
en una de las categorías del reporte y agrega conteos con ejemplos. Lo usan
el contexto del reporte (entorno/atractores), y el frontend lo recibe vía
payload (``entorno_comercial.categorias``).

Categorías y rangos SCIAN (intervalos cerrados sobre el código numérico):

1. ``similares`` — NO es un rango: es la clase SCIAN exacta del giro
   analizado (competencia directa). ``categoria_de`` nunca la devuelve;
   la calcula ``conteo_por_categoria(..., scian_giro=...)`` como sobrecapa.
2. ``restaurantes`` — Restaurantes, cafés y pastelerías:
   722110–722999 (preparación de alimentos y bebidas) y 311812
   (panificación tradicional, incl. pastelerías).
3. ``compras_diarias`` — Compras y servicios diarios: comercio al por menor
   461000–469999 no capturado por otra categoría (abarrotes 4611xx,
   autoservicio 4621xx, departamentales 4622xx, ropa/calzado 463xxx,
   artículos para el hogar 466/467xxx, misceláneas 469xxx), más 464xxx no
   farmacéutico.
4. ``salud`` — Hospitales y farmacias: 464111–464119 (farmacias),
   621000–623999 (consultorios, hospitales 622xxx, residencias de salud).
5. ``educacion`` — Escuelas y universidades: 611000–611999.
6. ``bancos`` — Bancos: 521000–522999 (banca central, banca múltiple
   522110, banca de desarrollo, cajas y uniones de crédito).
7. ``gimnasios`` — Gimnasios: 713940–713949 (gimnasios y clubes deportivos).
8. ``especializados`` — Servicios especializados: 541000–541999 (servicios
   profesionales), 561000–562999 (apoyo a negocios), 811000–814999
   (reparación, servicios personales 812xxx — tintorerías 812320,
   lavanderías, barberías 812110 —, servicios domésticos y religiosos).
9. ``plazas_gasolineras`` — Plazas y gasolineras: 468411–468419
   (gasolineras), 531110–531119 (administración de inmuebles / plazas
   comerciales como unidad económica registrada).

El orden de evaluación es de lo específico a lo general (farmacias y
gasolineras antes que el comercio al por menor genérico).
"""
from __future__ import annotations

from collections.abc import Iterable

#: (id, etiqueta) de las 9 categorías, en el orden del reporte.
CATEGORIAS: list[tuple[str, str]] = [
    ("similares", "Similares (mismo giro)"),
    ("restaurantes", "Restaurantes, cafés y pastelerías"),
    ("compras_diarias", "Compras y servicios diarios"),
    ("salud", "Hospitales y farmacias"),
    ("educacion", "Escuelas y universidades"),
    ("bancos", "Bancos"),
    ("gimnasios", "Gimnasios"),
    ("especializados", "Servicios especializados"),
    ("plazas_gasolineras", "Plazas y gasolineras"),
]

ETIQUETAS: dict[str, str] = dict(CATEGORIAS)

#: Categorías que atraen tráfico peatonal/vehicular (para atractores).
CATEGORIAS_ATRACTORAS = {
    "restaurantes", "compras_diarias", "salud", "educacion",
    "bancos", "gimnasios", "plazas_gasolineras",
}


def _en(scian_num: int, *intervalos: tuple[int, int]) -> bool:
    return any(a <= scian_num <= b for a, b in intervalos)


def categoria_de(scian: str | None) -> str | None:
    """Categoría del entorno para una clase SCIAN, o None si no clasifica.

    Nunca devuelve ``similares`` (depende del giro analizado, no del SCIAN
    en sí); ver el docstring del módulo.
    """
    if not scian:
        return None
    try:
        n = int(str(scian).strip())
    except (TypeError, ValueError):
        return None
    # Específicas primero (evitan caer en comercio genérico 46xxxx).
    if _en(n, (464111, 464119), (621000, 623999)):
        return "salud"
    if _en(n, (468411, 468419), (531110, 531119)):
        return "plazas_gasolineras"
    if _en(n, (521000, 522999)):
        return "bancos"
    if _en(n, (611000, 611999)):
        return "educacion"
    if _en(n, (713940, 713949)):
        return "gimnasios"
    if _en(n, (722110, 722999)) or n == 311812:
        return "restaurantes"
    if _en(n, (541000, 541999), (561000, 562999), (811000, 814999)):
        return "especializados"
    if _en(n, (461000, 469999)):
        return "compras_diarias"
    return None


def _campo(est: object, *nombres: str):
    """Lee un campo de un dict o de un objeto (fila DENUE flexible)."""
    for nombre in nombres:
        if isinstance(est, dict):
            if est.get(nombre) is not None:
                return est[nombre]
        else:
            valor = getattr(est, nombre, None)
            if valor is not None:
                return valor
    return None


def conteo_por_categoria(
    establecimientos: Iterable,
    scian_giro: str | None = None,
    top_ejemplos: int = 3,
) -> dict:
    """Agrega establecimientos por categoría con conteo y top de ejemplos.

    :param establecimientos: dicts u objetos con ``scian_code`` (o
        ``scian``) y ``nombre``.
    :param scian_giro: clase SCIAN del giro analizado; los establecimientos
        de esa clase cuentan además como ``similares``.
    Devuelve ``{"total": int, "categorias": [{categoria, etiqueta, conteo,
    ejemplos}]}`` con las 9 categorías siempre presentes (conteo 0 si no
    hay), para que la UI pinte la dona y los acordeones sin huecos.
    """
    conteos: dict[str, int] = {cid: 0 for cid, _ in CATEGORIAS}
    ejemplos: dict[str, list[str]] = {cid: [] for cid, _ in CATEGORIAS}
    total = 0
    for est in establecimientos:
        total += 1
        scian = _campo(est, "scian_code", "scian")
        nombre = _campo(est, "nombre", "name") or ""
        asignadas: list[str] = []
        if scian_giro and scian and str(scian) == str(scian_giro):
            asignadas.append("similares")
        cat = categoria_de(str(scian) if scian else None)
        if cat:
            asignadas.append(cat)
        for cid in asignadas:
            conteos[cid] += 1
            if nombre and len(ejemplos[cid]) < top_ejemplos:
                ejemplos[cid].append(str(nombre))
    return {
        "total": total,
        "categorias": [
            {
                "categoria": cid,
                "etiqueta": etiqueta,
                "conteo": conteos[cid],
                "ejemplos": ejemplos[cid],
            }
            for cid, etiqueta in CATEGORIAS
        ],
    }
