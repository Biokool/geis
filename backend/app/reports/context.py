"""Contexto completo del reporte de ubicación (Sección 1 · Sabueso).

``build_report_context`` agrega TODO desde la BD (AGEB del Censo y DENUE)
más los conectores OSM (Valhalla/Overpass) y devuelve el ``ctx`` completo
que ``app.reports.builder.build_location_report`` espera. Antes de esta
función, ``POST /reports`` solo pasaba anillos/TAM/Huff y 9 de las 14
secciones salían vacías (ver ``docs/INVENTARIO-SABUESO.md``).

Honestidad: cada bloque va en su propio try/except; si una fuente falla
o no tiene datos, su bloque sale vacío/nulo (el builder declara «dato no
disponible») y la fuente NO se cita en ``fuentes``. Nada se inventa.

Las consultas SQL llevan un comentario marcador (``/* ageb_agg */``, …)
para que los tests con sesiones fake puedan responder por tipo de
consulta sin Postgres real.
"""
from __future__ import annotations

import json

from sqlalchemy import text

from app.analytics.anclas import detectar_anclas
from app.analytics.categorias import (
    CATEGORIAS_ATRACTORAS,
    ETIQUETAS,
    categoria_de,
    conteo_por_categoria,
)
from app.analytics.movilidad import (
    actividad_economica,
    proxy_peatonal,
    proxy_vehicular,
)
from app.analytics.sector_data import buscar_ficha, ventas_equilibrio
from app.connectors.overpass import fetch_vialidades
from app.connectors.valhalla import fetch_isochrones
from app.db.session import safe_rollback

MAPS_URL = "https://www.google.com/maps/search/?api=1&query={lat},{lon}"


def _punto_wkt(lat: float, lon: float) -> str:
    return f"SRID=4326;POINT({lon} {lat})"


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


# ------------------------------------------------------------------ AGEB --
def _ageb_agg(db, lat: float, lon: float, radio_m: int) -> dict | None:
    """Agregados censales de las AGEB intersectadas por el radio mayor."""
    try:
        fila = db.execute(
            text(
                "/* ageb_agg */ SELECT "
                "COALESCE(SUM(pob_total),0), COALESCE(SUM(pob_femenina),0), "
                "COALESCE(SUM(pob_masculina),0), COALESCE(SUM(pob_0_14),0), "
                "COALESCE(SUM(pob_15_29),0), COALESCE(SUM(pob_30_59),0), "
                "COALESCE(SUM(pob_60_mas),0), "
                "COALESCE(SUM(pob_sin_clasificar),0), "
                "COALESCE(SUM(pea_ocupada),0), "
                "COALESCE(SUM(viv_habitadas),0), "
                "CASE WHEN SUM(viv_habitadas) > 0 THEN "
                "SUM(prom_ocupantes_viv * viv_habitadas)/SUM(viv_habitadas) END, "
                "CASE WHEN SUM(viv_habitadas) > 0 THEN "
                "SUM(pct_viv_internet * viv_habitadas)/SUM(viv_habitadas) END, "
                "CASE WHEN SUM(viv_habitadas) > 0 THEN "
                "SUM(pct_viv_computadora * viv_habitadas)/SUM(viv_habitadas) END, "
                "CASE WHEN SUM(viv_habitadas) > 0 THEN "
                "SUM(pct_viv_automovil * viv_habitadas)/SUM(viv_habitadas) END "
                "FROM prod.inegi_agebs WHERE ST_DWithin(geom::geography, "
                "ST_GeomFromEWKT(:punto)::geography, :radio)"
            ),
            {"punto": _punto_wkt(lat, lon), "radio": radio_m},
        ).first()
    except Exception:
        return None
    if fila is None:
        return None
    # Sin AGEB intersectada, SUM() devuelve 0 en una fila: eso NO es «0
    # habitantes», es «sin dato censal». Devolver None evita inventar ceros
    # y contradice el fallback de densidad que usa el análisis.
    if _f(fila[0]) <= 0 and _f(fila[9]) <= 0:
        return None
    return {
        "pob_total": _f(fila[0]), "pob_femenina": _f(fila[1]),
        "pob_masculina": _f(fila[2]), "pob_0_14": _f(fila[3]),
        "pob_15_29": _f(fila[4]), "pob_30_59": _f(fila[5]),
        "pob_60_mas": _f(fila[6]), "pob_sin_clasificar": _f(fila[7]),
        "pea_ocupada": _f(fila[8]), "viv_habitadas": _f(fila[9]),
        "prom_ocupantes": _f(fila[10]) if fila[10] is not None else None,
        "pct_internet": _f(fila[11]) if fila[11] is not None else None,
        "pct_computadora": _f(fila[12]) if fila[12] is not None else None,
        "pct_automovil": _f(fila[13]) if fila[13] is not None else None,
    }


def _nse_predominante(db, lat: float, lon: float, radio_m: int) -> str | None:
    """Banda NSE con mayor población entre las AGEB del radio (§3.9)."""
    try:
        filas = db.execute(
            text(
                "/* nse_banda */ SELECT nse_banda, "
                "COALESCE(SUM(pob_total),0) AS pob FROM prod.inegi_agebs "
                "WHERE ST_DWithin(geom::geography, "
                "ST_GeomFromEWKT(:punto)::geography, :radio) "
                "AND nse_banda IS NOT NULL "
                "GROUP BY nse_banda ORDER BY pob DESC"
            ),
            {"punto": _punto_wkt(lat, lon), "radio": radio_m},
        ).all()
    except Exception:
        return None
    if not filas:
        return None
    return filas[0][0]


# ------------------------------------------------------------------ DENUE --
def _denue_radio(db, lat: float, lon: float, radio_m: int,
                 limite: int = 500) -> list[dict]:
    """Establecimientos DENUE activos del radio, ordenados por distancia.

    El tope ``limite`` acota la lista que se usa para atractores/anclas y el
    desglose por categoría; el total del entorno se cuenta aparte con
    :func:`_denue_total` (sin tope).
    """
    try:
        filas = db.execute(
            text(
                "/* denue_radio */ SELECT nombre, scian_code, lat, lon, "
                "is_active, ST_Distance(geom::geography, "
                "ST_GeomFromEWKT(:punto)::geography) AS distancia_m "
                "FROM prod.denue_establishments "
                "WHERE is_active AND ST_DWithin(geom::geography, "
                "ST_GeomFromEWKT(:punto)::geography, :radio) "
                "ORDER BY distancia_m LIMIT :limite"
            ),
            {"punto": _punto_wkt(lat, lon), "radio": radio_m,
             "limite": limite},
        ).all()
    except Exception:
        return []
    return [
        {
            "nombre": f[0], "scian_code": f[1],
            "lat": _f(f[2]), "lon": _f(f[3]),
            "is_active": bool(f[4]), "distancia_m": _f(f[5]),
        }
        for f in filas
    ]


def _denue_total(db, lat: float, lon: float, radio_m: int) -> int | None:
    """Total real de establecimientos activos en el radio (sin tope)."""
    try:
        n = db.execute(
            text(
                "/* denue_total */ SELECT COUNT(*) "
                "FROM prod.denue_establishments "
                "WHERE is_active AND ST_DWithin(geom::geography, "
                "ST_GeomFromEWKT(:punto)::geography, :radio)"
            ),
            {"punto": _punto_wkt(lat, lon), "radio": radio_m},
        ).scalar()
    except Exception:
        return None
    return int(n or 0)


def _competencia_lista(db, lat: float, lon: float, radio_m: int,
                       scian: str) -> list[dict]:
    """Competidores (misma clase SCIAN) con nombre, distancia y estado."""
    try:
        filas = db.execute(
            text(
                "/* competencia_lista */ SELECT nombre, lat, lon, is_active, "
                "ST_Distance(geom::geography, "
                "ST_GeomFromEWKT(:punto)::geography) AS distancia_m "
                "FROM prod.denue_establishments "
                "WHERE scian_code = :scian AND ST_DWithin(geom::geography, "
                "ST_GeomFromEWKT(:punto)::geography, :radio) "
                "ORDER BY distancia_m LIMIT 50"
            ),
            {"scian": scian, "punto": _punto_wkt(lat, lon), "radio": radio_m},
        ).all()
    except Exception:
        return []
    lista = []
    for f in filas:
        activo = bool(f[3])
        lista.append({
            "nombre": f[0],
            "distancia_m": round(_f(f[4]), 1),
            "estado": "PARECE ACTIVO" if activo else "SIN ACTIVIDAD RECIENTE",
            "is_active": activo,
            "url_maps": MAPS_URL.format(lat=_f(f[1]), lon=_f(f[2])),
        })
    return lista


# --------------------------------------------------------------- isócronas --
def _enriquecer_isocronas(db, isocronas: list[dict], scian: str) -> list[dict]:
    """Población AGEB (prorrateo por área) y competidores por polígono."""
    for iso in isocronas:
        iso.setdefault("poblacion", None)
        iso.setdefault("competidores", None)
        geom = iso.get("geometria")
        if not geom:
            continue
        geojson = json.dumps(geom)
        try:
            pob = db.execute(
                text(
                    "/* isocrona_pob */ SELECT COALESCE(SUM(pob_total * "
                    "ST_Area(ST_Intersection(geom, "
                    "ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326))) / "
                    "NULLIF(ST_Area(geom), 0)), 0) FROM prod.inegi_agebs "
                    "WHERE ST_Intersects(geom, "
                    "ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326))"
                ),
                {"g": geojson},
            ).scalar()
            iso["poblacion"] = round(_f(pob), 1)
        except Exception:
            pass
        try:
            n = db.execute(
                text(
                    "/* isocrona_comp */ SELECT COUNT(*) "
                    "FROM prod.denue_establishments "
                    "WHERE scian_code = :scian AND is_active AND "
                    "ST_Intersects(geom, "
                    "ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326))"
                ),
                {"scian": scian, "g": geojson},
            ).scalar()
            iso["competidores"] = int(n or 0)
        except Exception:
            safe_rollback(db)
    return isocronas


# ---------------------------------------------------------------- editorial --
def _perfil_editorial(db, giro: str | None, ficha: dict | None) -> str | None:
    """Editorial del giro: ficha sectorial → knowledge_facts → None."""
    if ficha and ficha.get("editorial"):
        return ficha["editorial"]
    if not giro:
        return None
    try:
        fila = db.execute(
            text(
                "/* knowledge_editorial */ SELECT fact_value "
                "FROM knowledge_facts WHERE fact_key ILIKE :k LIMIT 1"
            ),
            {"k": f"%editorial%{giro}%"},
        ).first()
    except Exception:
        safe_rollback(db)
        return None
    if not fila:
        return None
    valor = fila[0]
    if isinstance(valor, dict):
        return valor.get("editorial") or valor.get("texto")
    return str(valor) if valor else None


# -------------------------------------------------------------------- main --
def build_report_context(
    db,
    *,
    giro: str | None,
    scian: str | None,
    lat: float,
    lon: float,
    radios: list[int],
    analisis: dict,
    etiqueta_ubicacion: str | None = None,
    con_geocoding: bool = False,
) -> dict:
    """Construye el ctx completo del builder desde BD + conectores OSM."""
    radios = list(radios) if radios else [1000, 2000]
    radio_max = max(radios)
    radio_min = min(radios)
    anillos = analisis.get("anillos") or []

    # ── Demanda y hogares (AGEB del radio mayor) ──────────────────────
    agg = _ageb_agg(db, lat, lon, radio_max)
    pob_total = agg["pob_total"] if agg else 0.0

    def _seg(nombre: str, pob: float) -> dict:
        return {
            "segmento": nombre,
            "poblacion": int(round(pob)),
            "pct": round(100.0 * pob / pob_total, 1) if pob_total else None,
        }

    if agg:
        demanda = {
            "poblacion_total": int(round(pob_total)),
            "poblacion_objetivo": int(round(agg["pob_30_59"])),
            "segmentos": [
                _seg("0 a 14 años", agg["pob_0_14"]),
                _seg("15 a 29 años", agg["pob_15_29"]),
                _seg("30 a 59 años", agg["pob_30_59"]),
                _seg("60 años y más", agg["pob_60_mas"]),
            ],
            "detalle_edad_sexo": {
                "grupos_edad": {
                    "0_14": int(round(agg["pob_0_14"])),
                    "15_29": int(round(agg["pob_15_29"])),
                    "30_59": int(round(agg["pob_30_59"])),
                    "60_mas": int(round(agg["pob_60_mas"])),
                    "sin_clasificar": int(round(agg["pob_sin_clasificar"])),
                },
                "por_sexo": {
                    "femenina": int(round(agg["pob_femenina"])),
                    "masculina": int(round(agg["pob_masculina"])),
                },
                "pea_ocupada": int(round(agg["pea_ocupada"])),
                "radio_m": radio_max,
            },
        }
        hogares = {
            "viviendas_habitadas": int(round(agg["viv_habitadas"])),
            "promedio_ocupantes": (
                round(agg["prom_ocupantes"], 2)
                if agg["prom_ocupantes"] is not None else None
            ),
            "pct_internet": (
                round(agg["pct_internet"], 1)
                if agg["pct_internet"] is not None else None
            ),
            "pct_computadora": (
                round(agg["pct_computadora"], 1)
                if agg["pct_computadora"] is not None else None
            ),
            "pct_automovil": (
                round(agg["pct_automovil"], 1)
                if agg["pct_automovil"] is not None else None
            ),
        }
        pob_15_mas = pob_total - agg["pob_0_14"]
    else:
        demanda = {"segmentos": [], "detalle_edad_sexo": {}}
        hogares = {}
        pob_15_mas = None

    # ── NSE predominante (§3.9: banda AGEB, referencia AMAI 2024) ─────
    banda = _nse_predominante(db, lat, lon, radio_max)
    nse_etiqueta = f"{banda} (referencia AMAI 2024)" if banda else None

    # ── Entorno, atractores y anclas (DENUE activo del radio mayor) ────
    denue_rows = _denue_radio(db, lat, lon, radio_max)
    total_denue = _denue_total(db, lat, lon, radio_max)
    entorno_agg = conteo_por_categoria(denue_rows, scian_giro=scian)
    entorno = {
        # Total real (COUNT sin tope); el desglose por categoría se calcula
        # sobre la lista acotada de 500 activos más cercanos y se declara.
        "total_negocios": (
            total_denue if total_denue is not None else entorno_agg["total"]
        ),
        "categorias": entorno_agg["categorias"],
        "radio_m": radio_max,
        "solo_activos": True,
        "nota": (
            "Negocios activos en el radio mayor. El desglose por categoría "
            "usa los 500 establecimientos activos más cercanos."
            if total_denue is not None and total_denue > len(denue_rows)
            else "Negocios activos en el radio mayor."
        ),
    }
    atractores: list[dict] = []
    for row in denue_rows:
        cat = categoria_de(row["scian_code"])
        if cat not in CATEGORIAS_ATRACTORAS:
            continue
        atractores.append({
            "nombre": row["nombre"],
            "categoria": cat,
            "categoria_etiqueta": ETIQUETAS.get(cat, cat),
            "distancia_m": round(row["distancia_m"], 1),
            "url_maps": MAPS_URL.format(lat=row["lat"], lon=row["lon"]),
        })
        if len(atractores) >= 15:
            break

    anclas = analisis.get("anclas") or detectar_anclas(denue_rows)

    # ── Competencia: lista + diferencial del anillo exterior ──────────
    competencia_lista = (
        _competencia_lista(db, lat, lon, radio_max, scian) if scian else []
    )
    conteo_por_radio = {a.get("radio_m"): a.get("competencia") or 0
                        for a in anillos}
    anillo_1_2_km = None
    if radio_min in conteo_por_radio and radio_max in conteo_por_radio \
            and radio_max > radio_min:
        anillo_1_2_km = conteo_por_radio[radio_max] - conteo_por_radio[radio_min]

    # ── Vialidades (Overpass) y movilidad (§3.10, siempre estimado) ────
    try:
        vialidades = fetch_vialidades(lat, lon, radio_m=2000)
    except Exception:
        vialidades = []
    movilidad = {
        "vehicular": proxy_vehicular(vialidades, pob_total),
        "peatonal": proxy_peatonal(
            pob_total, radio_m=radio_max,
            pea_ocupada=agg["pea_ocupada"] if agg else 0.0,
            n_atractores=len(atractores),
        ),
        "actividad": actividad_economica(
            agg["pea_ocupada"] if agg else None,
            pob_total if agg else None,
            pob_15_mas,
        ),
    }

    # ── Isócronas Valhalla (fallback honesto: radios) ──────────────────
    try:
        isocronas_crudas = fetch_isochrones(lat, lon)
    except Exception:
        isocronas_crudas = []
    isocronas = (
        _enriquecer_isocronas(db, isocronas_crudas, scian)
        if isocronas_crudas and scian else isocronas_crudas
    )
    alcance_tipo = "isocronas" if isocronas else "radios"

    # ── Sectorial: editorial, datos del giro, delivery, break-even ────
    ficha = buscar_ficha(giro)
    sector = None
    delivery = {"aplica": False}
    break_even = None
    if ficha:
        sector = {**ficha["sector"], "giro": ficha["nombre"],
                  "scian": ficha["scian"]}
        break_even = {
            **ficha["break_even"],
            "ventas_equilibrio_mensual": ventas_equilibrio(ficha),
            "renta_formula": "Renta_mensual = Precio_m2 × Superficie_m2 (§3.12.1)",
        }
        if ficha["delivery"]:
            delivery = {
                "aplica": True,
                "radio_inicial_km": [2, 3],
                "tiempo_objetivo_min": [30, 35],
                "delivery_pct": ficha["sector"]["delivery_pct"],
                "nota": "Radio inicial sugerido 2–3 km con entrega en "
                        "menos de 30–35 min (plantilla del giro, editable).",
            }
    perfil_editorial = _perfil_editorial(db, giro, ficha)

    # ── Fuentes nominales efectivamente usadas ─────────────────────────
    fuentes: list[dict] = []
    if agg:
        fuentes.append({
            "fuente": "INEGI Censo 2020 (AGEB)",
            "rol": "Población por edad/sexo, hogares, PEA ocupada y banda "
                   "NSE proxy (§3.9)",
        })
    if denue_rows or competencia_lista:
        fuentes.append({
            "fuente": "DENUE (INEGI)",
            "rol": "Entorno comercial, competencia, atractores y anclas "
                   "por distancia",
        })
    if con_geocoding:
        fuentes.append({
            "fuente": "Geocoding OpenStreetMap/Nominatim",
            "rol": "Resolución de la dirección y etiqueta legible "
                   "(colonia/municipio/entidad)",
        })
    if isocronas:
        fuentes.append({
            "fuente": "Isócronas Valhalla/OSM",
            "rol": "Alcance por tiempo (5 min peatón, 10 moto, 15 auto)",
        })
    if vialidades:
        fuentes.append({
            "fuente": "Vialidades OpenStreetMap (Overpass)",
            "rol": "Vías principales cercanas e insumos del proxy de "
                   "movilidad (§3.10)",
        })
    fuentes.append({
        "fuente": "Cálculos propios GEIS",
        "rol": "ISM, Huff (con efecto ancla), TAM y proxies de movilidad "
               "etiquetados como estimados",
    })

    return {
        "giro": analisis.get("giro", giro),
        "scian": analisis.get("scian", scian),
        "lat": lat, "lon": lon,
        "etiqueta_ubicacion": etiqueta_ubicacion,
        "radios": radios,
        "anillos": anillos,
        "tam_mxn": analisis.get("tam_mxn"),
        "tam_rango": analisis.get("tam_rango", (None, None)),
        "huff": analisis.get("huff", {}),
        "advertencias": analisis.get("advertencias", []),
        "demanda": demanda,
        "hogares": hogares,
        "nse_etiqueta": nse_etiqueta,
        "nse_banda": banda,
        "nse_referencia": "AMAI 2024" if banda else None,
        "entorno": entorno,
        "competencia_lista": competencia_lista,
        "competencia_anillo_1_2_km": anillo_1_2_km,
        "atractores": atractores,
        "anclas": anclas,
        "perfil_editorial": perfil_editorial,
        "sector": sector,
        "delivery": delivery,
        "break_even": break_even,
        "isocronas": isocronas,
        "alcance_tipo": alcance_tipo,
        "vialidades": vialidades,
        "movilidad": movilidad,
        "fuentes": fuentes,
    }
