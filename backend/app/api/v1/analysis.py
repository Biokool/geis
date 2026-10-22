"""Router de análisis: viabilidad de ubicación (CU-2), prospección B2B (CU-1) y look-alike (CU-3).

Usa las fórmulas reales del SRS §3 (ISM, Huff, TAM, IDT, score B2B).
"""
from __future__ import annotations

import math

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics import (
    accesibilidad_logistica,
    b2b_score,
    captura,
    completitud_contacto,
    e_estrato,
    idt,
    ism,
    ism_band,
    p_ij,
    p_ij_rango,
    rango,
    tam,
)
from app.api.v1._common import lineage
from app.db.session import get_db
from app.reports.builder import decidir_veredicto
from app.models.investigations import UserInvestigation
from app.schemas.analysis import (
    B2BLeadResult,
    B2BRequest,
    B2BResponse,
    CompareItem,
    CompareRequest,
    CompareResponse,
    LocationAnalysisRequest,
    LocationAnalysisResponse,
    LookalikeItem,
    LookalikeRequest,
    LookalikeResponse,
    RingResult,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])

#: Benchmarks ISM por defecto (ejemplo SRS §3.1); fase 2: por ciudad/giro en model_params.
ISM_P50_DEFAULT = 280.0
ISM_P90_DEFAULT = 520.0

#: Supuestos editables del TAM cuando no hay catálogo sectorial (TAM-01).
TAM_SUPUESTOS_DEFAULT = {
    "gasto_pc_mxn_anual": 2400.0,
    "f_nse": 1.15,
    "f_pen": 0.45,
    "fuente": "supuesto editable (catálogo sectorial en fase 2)",
}

#: Demanda climática por defecto (IDT): 0.6 templado; fase 2: catálogo por municipio.
CLIMA_DEFAULT = 0.6


def _punto_wkt(lat: float, lon: float) -> str:
    return f"SRID=4326;POINT({lon} {lat})"


def resolver_scian(db: Session, giro: str | None, scian: str | None) -> tuple[str, str | None, list[str]]:
    """Resuelve la clase SCIAN desde `scian` directo o desde `giro` en texto libre."""
    advertencias: list[str] = []
    if scian:
        existe = db.execute(
            text("SELECT description FROM prod.cat_scian WHERE scian_code = :s"),
            {"s": scian},
        ).first()
        if not existe:
            raise HTTPException(status_code=422, detail=f"SCIAN {scian} no está en el catálogo")
        return scian, giro, advertencias
    if giro:
        fila = db.execute(
            text(
                "SELECT scian_code FROM prod.cat_giro_scian "
                "WHERE giro_label ILIKE :g ORDER BY confidence DESC LIMIT 1"
            ),
            {"g": f"%{giro}%"},
        ).first()
        if fila:
            return fila[0], giro, advertencias
        advertencias.append(
            f"Giro '{giro}' sin mapeo en cat_giro_scian; se usa la clase genérica 722515"
        )
        return "722515", giro, advertencias
    raise HTTPException(status_code=422, detail="Se requiere `giro` o `scian`")


def competencia_por_radio(db: Session, lat: float, lon: float, radio_m: int, scian: str) -> int:
    """Cuenta competencia directa (misma clase SCIAN) dentro del radio (ISM-03)."""
    return db.execute(
        text(
            "SELECT COUNT(*) FROM prod.denue_establishments "
            "WHERE scian_code = :scian AND is_active "
            "AND ST_DWithin(geom::geography, "
            "ST_GeomFromEWKT(:punto)::geography, :radio)"
        ),
        {"scian": scian, "punto": _punto_wkt(lat, lon), "radio": radio_m},
    ).scalar() or 0


def demanda_pob_3059(db: Session, lat: float, lon: float, radio_m: int) -> tuple[float, str]:
    """Demanda D: población 30–59 de AGEB intersectadas; fallback determinista."""
    total = db.execute(
        text(
            "SELECT COALESCE(SUM(pob_30_59), 0) FROM prod.inegi_agebs "
            "WHERE ST_DWithin(geom::geography, "
            "ST_GeomFromEWKT(:punto)::geography, :radio)"
        ),
        {"punto": _punto_wkt(lat, lon), "radio": radio_m},
    ).scalar() or 0
    if total > 0:
        return float(total), "observada (AGEB intersectadas, Censo)"
    # Fallback determinista: densidad urbana típica × área del círculo.
    area_km2 = math.pi * (radio_m / 1000.0) ** 2
    return round(area_km2 * 11000, 1), "fallback determinista (sin AGEB en la zona)"


def compute_location_analysis(
    db: Session, giro: str | None, scian: str | None,
    lat: float, lon: float, radios: list[int],
) -> dict:
    """Núcleo del análisis de ubicación (reutilizado por el builder de reportes)."""
    scian_code, giro_label, advertencias = resolver_scian(db, giro, scian)

    # Atractivo base y lambda del catálogo (HUFF-01).
    cat = db.execute(
        text("SELECT base_attractiveness, lambda_default FROM prod.cat_scian WHERE scian_code = :s"),
        {"s": scian_code},
    ).first()
    atractivo_candidato = float(cat[0]) if cat else 0.7
    lambda_giro = float(cat[1]) if cat else 2.0

    anillos: list[dict] = []
    for radio in radios:
        oferta = competencia_por_radio(db, lat, lon, radio, scian_code)
        demanda, fuente_demanda = demanda_pob_3059(db, lat, lon, radio)
        valor_ism = ism(demanda, oferta)
        banda = ism_band(valor_ism, ISM_P50_DEFAULT, ISM_P90_DEFAULT)
        anillos.append({
            "radio_m": radio, "competencia": oferta,
            "demanda_pob_30_59": demanda, "ism": round(valor_ism, 1),
            "ism_banda": banda, "fuente_demanda": fuente_demanda,
        })

    # TAM con el radio mayor (TAM-02: siempre con rango).
    demanda_tam = anillos[-1]["demanda_pob_30_59"] if anillos else 0.0
    sup = dict(TAM_SUPUESTOS_DEFAULT)
    valor_tam = tam(demanda_tam, sup["gasto_pc_mxn_anual"], sup["f_nse"], sup["f_pen"])
    rango_tam = rango(valor_tam)

    # Huff: cuota del punto candidato frente a los 20 competidores más cercanos.
    comp = db.execute(
        text(
            "SELECT c.base_attractiveness, "
            "ST_Distance(d.geom::geography, ST_GeomFromEWKT(:punto)::geography) AS dist_m "
            "FROM prod.denue_establishments d "
            "JOIN prod.cat_scian c ON c.scian_code = d.scian_code "
            "WHERE d.scian_code = :scian AND d.is_active "
            "AND ST_DWithin(d.geom::geography, ST_GeomFromEWKT(:punto)::geography, :radio) "
            "ORDER BY dist_m LIMIT 20"
        ),
        {"scian": scian_code, "punto": _punto_wkt(lat, lon), "radio": max(radios) if radios else 2000},
    ).all()
    dist_candidato_km = 0.2  # consumidor representativo a 200 m del punto
    competidores = [(float(a or 0.5), max(float(dm) / 1000.0, 0.05)) for a, dm in comp]
    cuota = p_ij(atractivo_candidato, dist_candidato_km, competidores, alpha=1.0, lambda_=lambda_giro)
    cuota_rango = p_ij_rango(atractivo_candidato, dist_candidato_km, competidores, alpha=1.0, lambda_=lambda_giro)
    captura_mxn = captura(valor_tam, cuota)

    veredicto, confianza, factores = decidir_veredicto(anillos)
    if any("fallback" in a["fuente_demanda"] for a in anillos):
        advertencias.append("Demanda estimada con fallback determinista: cargar AGEB del Censo para cifras observadas")
    advertencias.append("El TAM es el tamaño del mercado, no las ventas del punto (TAM-03)")

    return {
        "giro": giro_label, "scian": scian_code, "lat": lat, "lon": lon,
        "anillos": anillos,
        "tam_mxn": round(valor_tam, 2), "tam_rango": (round(rango_tam[0], 2), round(rango_tam[1], 2)),
        "tam_supuestos": sup,
        "huff": {
            "cuota_punto": round(cuota, 4), "rango_cuota": [round(cuota_rango[0], 4), round(cuota_rango[2], 4)],
            "alpha": 1.0, "lambda": lambda_giro,
            "captura_mxn_anual": round(captura_mxn, 2),
            "n_competidores_modelo": len(competidores),
        },
        "veredicto": veredicto, "confianza": confianza, "factores": factores,
        "advertencias": advertencias,
    }


@router.post("/location", response_model=LocationAnalysisResponse)
def location_analysis(body: LocationAnalysisRequest, db: Session = Depends(get_db)):
    """Análisis de viabilidad de ubicación (CU-2): ISM por anillo, TAM y Huff."""
    r = compute_location_analysis(db, body.giro, body.scian, body.lat, body.lon, body.radios)
    return LocationAnalysisResponse(
        giro=r["giro"], scian=r["scian"], lat=r["lat"], lon=r["lon"],
        anillos=[RingResult(**a) for a in r["anillos"]],
        tam_mxn=r["tam_mxn"], tam_rango_mxn=r["tam_rango"],
        huff_cuota_punto=r["huff"]["cuota_punto"],
        veredicto=r["veredicto"], factores=r["factores"],
        advertencias=r["advertencias"], lineage=lineage(db),
    )


@router.post("/compare", response_model=CompareResponse)
def comparar_investigaciones(body: CompareRequest, db: Session = Depends(get_db)):
    """Compara de 2 a 5 investigaciones recalculando su análisis de ubicación.

    Por cada investigación se reutiliza ``compute_location_analysis`` con el
    giro/SCIAN guardados en ``params`` y los radios guardados en ``radii_m``
    (o [1000, 2000] si no hay). El resumen de cada item toma ISM, competencia
    y población del anillo de mayor radio.
    """
    items: list[CompareItem] = []
    for investigation_id in body.investigation_ids:
        inv = db.get(UserInvestigation, investigation_id)
        if inv is None:
            raise HTTPException(
                status_code=404,
                detail=f"Investigación {investigation_id} no encontrada",
            )
        if inv.center_lat is None or inv.center_lon is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"La investigación {investigation_id} "
                    f"('{getattr(inv, 'title', '')}') no tiene centro "
                    "(center_lat/center_lon) para comparar"
                ),
            )
        params = inv.params or {}
        resultado = compute_location_analysis(
            db,
            giro=params.get("giro"),
            scian=params.get("scian"),
            lat=float(inv.center_lat),
            lon=float(inv.center_lon),
            radios=list(inv.radii_m) if inv.radii_m else [1000, 2000],
        )
        anillos = resultado.get("anillos") or []
        anillo_mayor = anillos[-1] if anillos else {}
        items.append(CompareItem(
            id=str(getattr(inv, "investigation_id", investigation_id)),
            nombre=inv.title,
            territorio=inv.territory_kind,
            center_lat=float(inv.center_lat),
            center_lon=float(inv.center_lon),
            veredicto=resultado["veredicto"],
            ism=float(anillo_mayor.get("ism", 0.0)),
            competencia=int(anillo_mayor.get("competencia", 0)),
            poblacion=float(anillo_mayor.get("demanda_pob_30_59", 0.0)),
            tam=float(resultado["tam_mxn"]),
            huff_score=float(resultado["huff"]["cuota_punto"]),
        ))
    return CompareResponse(items=items, lineage=lineage(db))


# ------------------------------------------------------------------ B2B ----
def _intensidad_scian(db: Session, scian_code: str) -> float:
    fila = db.execute(
        text("SELECT thermal_intensity FROM prod.cat_scian WHERE scian_code = :s"),
        {"s": scian_code},
    ).first()
    return float(fila[0]) if fila else 0.5


@router.post("/b2b-prospecting", response_model=B2BResponse)
def b2b_prospecting(body: B2BRequest, db: Session = Depends(get_db)):
    """Prospección B2B (CU-1): leads con IDT y score calculados de verdad."""
    filtros = ["is_active",
               "estrato_ordinal >= :estrato_min",
               "ST_DWithin(geom::geography, ST_GeomFromEWKT(:punto)::geography, :radio)"]
    params: dict = {
        "estrato_min": body.estrato_min_ord,
        "punto": _punto_wkt(body.lat, body.lon),
        "radio": body.radio_m,
    }
    if body.scian:
        filtros.append("scian_code = ANY(:scians)")
        params["scians"] = body.scian

    filas = db.execute(
        text(
            "SELECT denue_id, nombre, scian_code, estrato_texto, estrato_ordinal, "
            "telefono, correo, sitio_web, "
            "ST_Distance(geom::geography, ST_GeomFromEWKT(:punto)::geography) AS dist_m "
            f"FROM prod.denue_establishments WHERE {' AND '.join(filtros)} "
            "ORDER BY dist_m LIMIT 500"
        ),
        params,
    ).all()

    leads: list[dict] = []
    for f in filas:
        denue_id, nombre, scian_code, estrato_txt, estrato_ord, tel, correo, sitio, dist_m = f
        resultado_idt = idt(
            int(estrato_ord), _intensidad_scian(db, scian_code),
            CLIMA_DEFAULT, None,  # antigüedad desconocida → 0.5 neutro
        )
        componentes = {
            "idt": resultado_idt["idt"] / 100.0,
            "tamano": e_estrato(int(estrato_ord)),
            "accesibilidad": accesibilidad_logistica(float(dist_m) / 1000.0),
            "densidad": min(len(filas) / 100.0, 1.0),
            "contacto": completitud_contacto(bool(tel), bool(correo), bool(sitio)),
        }
        s = b2b_score(componentes)
        leads.append({
            "denue_id": denue_id, "nombre": nombre, "scian_code": scian_code,
            "estrato_texto": estrato_txt, "distancia_m": round(float(dist_m), 1),
            "idt": resultado_idt["idt"], "score": s["score"], "desglose": s["desglose"],
        })
    # SC-03: empates se rompen por IDT y luego por distancia.
    leads.sort(key=lambda l: (-l["score"], -l["idt"], l["distancia_m"]))

    return B2BResponse(
        total_candidatos=len(leads),
        leads=[B2BLeadResult(**l) for l in leads[: body.top_n]],
        lineage=lineage(db),
    )


# -------------------------------------------------------------- look-alike --
VARIABLES_LOOKALIKE = [
    "pob_total", "pob_30_59", "viv_habitadas",
    "pct_viv_internet", "pct_viv_automovil", "nse_score",
]


@router.post("/lookalike", response_model=LookalikeResponse)
def lookalike(body: LookalikeRequest, db: Session = Depends(get_db)):
    """Expansión por similitud (CU-3): distancia coseno sobre vectores AGEB (§3.8)."""
    cols = ", ".join(VARIABLES_LOOKALIKE)
    semillas = db.execute(
        text(f"SELECT cvegeo, {cols} FROM prod.inegi_agebs WHERE cvegeo = ANY(:s)"),
        {"s": body.semillas},
    ).all()
    if not semillas:
        # Stub con estructura real cuando no hay AGEB semilla en la BD.
        return LookalikeResponse(
            ranking=[
                LookalikeItem(cvegeo=f"09033000100{i}", similitud=round(0.95 - i * 0.03, 3),
                              top_variables=["pob_30_59", "nse_score", "viv_habitadas"])
                for i in range(1, min(body.top_n, 5) + 1)
            ],
            nota="Sin AGEB semilla en la BD: ranking de muestra con estructura real.",
            lineage=lineage(db),
        )

    vec_semilla = np.array(
        [[float(v or 0) for v in fila[1:]] for fila in semillas], dtype=float
    ).mean(axis=0)

    candidatos = db.execute(
        text(f"SELECT cvegeo, {cols} FROM prod.inegi_agebs WHERE NOT (cvegeo = ANY(:s)) LIMIT 2000"),
        {"s": body.semillas},
    ).all()
    if not candidatos:
        raise HTTPException(status_code=422, detail="No hay AGEB candidatas en la BD")

    mat = np.array([[float(v or 0) for v in fila[1:]] for fila in candidatos], dtype=float)
    # Normalización min-max por columna para que la escala no domine.
    mins = mat.min(axis=0)
    maxs = mat.max(axis=0)
    rng = np.where(maxs - mins > 0, maxs - mins, 1.0)
    mat_n = (mat - mins) / rng
    sem_n = (vec_semilla - mins) / rng

    def coseno(a: np.ndarray, b: np.ndarray) -> float:
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        return float(a @ b / (na * nb)) if na and nb else 0.0

    scored = []
    for fila, vec in zip(candidatos, mat_n):
        sim = coseno(sem_n, vec)
        # Variables que más explican la similitud (menor distancia por variable).
        orden = sorted(range(len(VARIABLES_LOOKALIKE)),
                       key=lambda i: abs(sem_n[i] - vec[i]))
        scored.append((fila[0], sim, [VARIABLES_LOOKALIKE[i] for i in orden[:3]]))
    scored.sort(key=lambda t: -t[1])

    return LookalikeResponse(
        ranking=[LookalikeItem(cvegeo=c, similitud=round(s, 4), top_variables=v)
                 for c, s, v in scored[: body.top_n]],
        lineage=lineage(db),
    )
