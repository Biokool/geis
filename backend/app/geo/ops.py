"""Operaciones geoespaciales: buffers geodésicos y SQL PostGIS (§4.4 del SRS)."""
from __future__ import annotations

from pyproj import Geod
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

#: Elipsoide WGS84 para cálculos geodésicos exactos.
_GEOD = Geod(ellps="WGS84")


def buffer_m(lat: float, lon: float, radius_m: float, segments: int = 64) -> Polygon:
    """Buffer geodésico (círculo real sobre el elipsoide) en WGS84.

    A diferencia de un buffer en grados, el radio en metros es exacto en
    cualquier latitud. Devuelve un polígono Shapely en lon/lat (EPSG:4326).
    """
    if radius_m <= 0:
        raise ValueError("radius_m debe ser > 0")
    if not -90 <= lat <= 90:
        raise ValueError("lat fuera de rango")
    puntos = [
        _GEOD.fwd(lon, lat, az, radius_m)[:2]
        for az in (i * 360.0 / segments for i in range(segments))
    ]
    return Polygon(puntos)


def buffer_wkt(lat: float, lon: float, radius_m: float, segments: int = 64) -> str:
    """WKT del buffer geodésico, listo para ST_GeomFromText(..., 4326)."""
    return buffer_m(lat, lon, radius_m, segments).wkt


def points_in_radius_query(
    table: str = "prod.denue_establishments",
    geom_col: str = "geom",
    extra_where: str = "",
    extra_cols: str = "denue_id, nombre, scian_code, estrato_ordinal, lat, lon",
) -> str:
    """Genera SQL PostGIS: puntos dentro de un radio usando geography.

    Usa ``ST_DWithin`` sobre ``geography`` para distancias en metros
    exactas. Parámetros nombrados: ``:lat``, ``:lon``, ``:radius_m``.

    :param extra_where: condición SQL adicional (p. ej. filtro por SCIAN).
    :param extra_cols: columnas a seleccionar además de la distancia.
    """
    where = f"AND ({extra_where})" if extra_where.strip() else ""
    return f"""
SELECT {extra_cols},
       ST_Distance(
           {geom_col}::geography,
           ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
       ) AS distance_m
FROM {table}
WHERE ST_DWithin(
          {geom_col}::geography,
          ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
          :radius_m
      )
  {where}
ORDER BY distance_m
""".strip()


def aggregate_by_rings_query(
    lat_col: str = "lat",
    table: str = "prod.denue_establishments",
    geom_col: str = "geom",
    rings: tuple[int, ...] = (1000, 2000),
    scian_filter: str = "",
) -> str:
    """Genera SQL que cuenta puntos por anillo concéntrico (ISM-03).

    Cada anillo se reporta por separado (no se promedian anillos).
    Parámetros nombrados: ``:lat``, ``:lon``.
    """
    inner_prev = 0
    cases = []
    for i, outer in enumerate(rings):
        etiqueta = f"{inner_prev}-{outer}m"
        cond = (
            f"ST_DWithin({geom_col}::geography, "
            f"ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, {outer})"
        )
        if inner_prev:
            cond += (
                f" AND NOT ST_DWithin({geom_col}::geography, "
                f"ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, {inner_prev})"
            )
        cases.append(f"SUM(CASE WHEN {cond} THEN 1 ELSE 0 END) AS anillo_{i}_{etiqueta}")
        inner_prev = outer
    where = f"WHERE {scian_filter}" if scian_filter.strip() else ""
    return f"SELECT {', '.join(cases)} FROM {table} {where}".strip()


def agebs_intersecting_buffer_query(rings: tuple[int, ...] = (1000, 2000)) -> str:
    """SQL: AGEB intersectadas por el buffer geodésico (para demanda D del ISM).

    Devuelve por AGEB las variables de demanda. Parámetros: ``:wkt`` (WKT del
    buffer) — se genera con :func:`buffer_wkt`.
    """
    return """
SELECT cvegeo, cve_ent, cve_mun, ambito,
       pob_total, pob_30_59, pob_15_29, pea_ocupada, viv_habitadas,
       nse_score, nse_banda
FROM prod.inegi_agebs
WHERE ST_Intersects(geom, ST_GeomFromText(:wkt, 4326))
""".strip()


def geometry_from_wkt(wkt: str) -> BaseGeometry:
    """Parsea un WKT a geometría Shapely (validación de entradas)."""
    from shapely import wkt as _wkt

    return _wkt.loads(wkt)
