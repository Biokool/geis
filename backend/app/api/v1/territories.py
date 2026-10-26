"""Router de territorios: geocodificación REAL y utilidades territoriales.

Se acabó el stub del Zócalo: una dirección se resuelve con Nominatim/OSM,
un link de Google Maps se parsea (o se sigue su redirect si es corto) y
si nada resuelve se responde 422 — nunca un punto falso. La etiqueta
legible (colonia, municipio, entidad) sale de la geocodificación inversa.

Las funciones de red viven en ``app.geo.geocoding`` y se importan a este
namespace para que los tests puedan mockearlas aquí mismo.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1._common import lineage
from app.db.session import get_db
from app.geo.geocoding import (
    componentes_de,
    es_link_corto,
    es_url,
    etiqueta_legible,
    nominatim_reverse,
    nominatim_search,
    parse_maps_link,
    resolve_short_link,
)
from app.schemas.territories import GeocodeRequest, GeocodeResponse

router = APIRouter(prefix="/territories", tags=["territories"])


def _reverse_seguro(lat: float, lon: float) -> dict:
    """Componentes del reverse; {} si el servicio no responde (no bloquea)."""
    try:
        datos = nominatim_reverse(lat, lon)
    except Exception:
        return {}
    if not datos:
        return {}
    return componentes_de(datos.get("address"))


def _respuesta(lat: float, lon: float, fuente: str, db: Session,
               direccion_formateada: str | None = None,
               componentes: dict | None = None) -> GeocodeResponse:
    """Arma la respuesta aplicando reverse si faltan componentes/etiqueta."""
    comp = dict(componentes or {})
    if not any(comp.get(k) for k in ("colonia", "municipio", "entidad")):
        comp = _reverse_seguro(lat, lon) or comp
    etiqueta = etiqueta_legible(comp, lat, lon)
    return GeocodeResponse(
        lat=lat, lon=lon, label=etiqueta, stub=False, fuente=fuente,
        direccion_formateada=direccion_formateada or etiqueta,
        colonia=comp.get("colonia"), municipio=comp.get("municipio"),
        entidad=comp.get("entidad"), cp=comp.get("cp"),
        lineage=lineage(db),
    )


@router.post("/geocode", response_model=GeocodeResponse)
def geocode(body: GeocodeRequest, db: Session = Depends(get_db)) -> GeocodeResponse:
    """Convierte {lat, lon} o {address} en un punto confirmado.

    ``address`` puede ser: coordenadas directas, un link de Google Maps
    (largo o corto) o una dirección en texto libre (Nominatim, solo MX).
    """
    if body.lat is not None and body.lon is not None:
        return _respuesta(body.lat, body.lon, "coordenadas", db)

    if body.address:
        texto = body.address.strip()

        # 1) Coordenadas embebidas (link de Maps largo o "lat, lon" suelto).
        punto = parse_maps_link(texto)
        if punto:
            return _respuesta(punto[0], punto[1], "link_maps", db)

        # 2) Link corto: seguir redirect y re-parsear la URL final.
        if es_link_corto(texto):
            destino = resolve_short_link(texto)
            punto = parse_maps_link(destino) if destino else None
            if punto:
                return _respuesta(punto[0], punto[1], "link_maps", db)
            raise HTTPException(
                status_code=422,
                detail="El link corto de Maps no resolvió a una ubicación; "
                       "pega el link completo o la dirección en texto.",
            )

        # 3) Otra URL sin coordenadas: no hay nada que geocodificar.
        if es_url(texto):
            raise HTTPException(
                status_code=422,
                detail="La URL no contiene coordenadas reconocibles de Google Maps.",
            )

        # 4) Dirección en texto → Nominatim.
        resultado = nominatim_search(texto)
        if not resultado:
            raise HTTPException(
                status_code=422,
                detail=f"No se pudo geocodificar la dirección: {texto!r}. "
                       "Verifica calle, número, colonia y ciudad.",
            )
        try:
            lat, lon = float(resultado["lat"]), float(resultado["lon"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail="El geocodificador devolvió un resultado sin coordenadas válidas.",
            )
        comp = componentes_de(resultado.get("address"))
        return _respuesta(
            lat, lon, "nominatim", db,
            direccion_formateada=resultado.get("display_name"),
            componentes=comp,
        )

    raise HTTPException(status_code=422, detail="Se requiere {lat, lon} o {address}")
