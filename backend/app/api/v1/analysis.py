"""Router de análisis: viabilidad de ubicación (CU-2), prospección B2B (CU-1) y look-alike (CU-3).

Usa las fórmulas reales del SRS §3 (ISM, Huff, TAM, IDT, score B2B).
"""
from __future__ import annotations

import math
import re

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
from app.analytics.anclas import aplicar_efecto_ancla, detectar_anclas
from app.analytics.sector_data import buscar_ficha
from app.api.v1._common import lineage
from app.db.session import get_db, safe_rollback
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
    """Resuelve la clase SCIAN desde `scian` directo o desde `giro` en texto libre.

    Un SCIAN capturado a mano (editable en la UI) **no** se rechaza si no
    está en ``prod.cat_scian``: se analiza con los parámetros neutros del
    catálogo (atractivo 0.7, lambda 2.0) y se avisa en ``advertencias``.
    Antes se respondía 422 y el flujo «2 campos + 1 clic» se rompía con
    clases válidas del DENUE que aún no estaban en el catálogo semilla.
    """
    advertencias: list[str] = []
    if scian:
        codigo = str(scian).strip()
        if not codigo.isdigit():
            match = re.search(r"\b(\d{6})\b", codigo)
            if match is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"SCIAN inválido: {scian!r} (debe incluir un código de 6 dígitos)",
                )
            codigo = match.group(1)
        existe = db.execute(
            text("SELECT description FROM prod.cat_scian WHERE scian_code = :s"),
            {"s": codigo},
        ).first()
        if not existe:
            advertencias.append(
                f"SCIAN {codigo} no está en el catálogo semilla: se usa "
                "atractivo 0.7 y lambda 2.0 por defecto. La competencia se "
                "cuenta igual contra el DENUE (misma clase SCIAN)."
            )
        return codigo, giro or (str(existe[0]) if existe else None), advertencias
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


def _anclas_cercanas(db: Session, lat: float, lon: float) -> list[dict]:
    """Negocios ancla cerca del punto (catálogo §3.12.3), o [] si falla.

    Silencioso a propósito: sin DENUE accesible no hay efecto ancla y el
    cálculo de Huff queda exactamente como antes.
    """
    try:
        filas = db.execute(
            text(
                "/* anclas */ SELECT nombre, scian_code, "
                "ST_Distance(geom::geography, "
                "ST_GeomFromEWKT(:punto)::geography) AS distancia_m "
                "FROM prod.denue_establishments "
                "WHERE is_active AND ST_DWithin(geom::geography, "
                "ST_GeomFromEWKT(:punto)::geography, 800) "
                "ORDER BY distancia_m LIMIT 300"
            ),
            {"punto": _punto_wkt(lat, lon)},
        ).all()
    except Exception:
        safe_rollback(db)
        return []
    return detectar_anclas([
        {"nombre": f[0], "scian_code": f[1],
         "distancia_m": float(f[2]) if f[2] is not None else None}
        for f in filas
    ])


def compute_location_analysis(
    db: Session, giro: str | None, scian: str | None,
    lat: float, lon: float, radios: list[int],
    tam_overrides: dict | None = None,
) -> dict:
    """Núcleo del análisis de ubicación (reutilizado por el builder de reportes).

    Supuestos TAM: si el giro tiene ficha en el catálogo sectorial se usan
    sus supuestos; ``tam_overrides`` (del request) gana sobre la ficha y
    sobre el default. Efecto ancla (§3.12.3): la atractividad del punto se
    multiplica por ``(1 + Σ w_a)`` con las anclas dentro de su radio.
    """
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
    ficha = buscar_ficha(giro_label)
    if ficha:
        sup = {
            "gasto_pc_mxn_anual": ficha["tam_supuestos"]["gasto_pc_mxn_anual"],
            "f_nse": ficha["tam_supuestos"]["f_nse"],
            "f_pen": ficha["tam_supuestos"]["f_pen"],
            "fuente": ficha["tam_supuestos"]["fuente"],
        }
    if tam_overrides:
        if tam_overrides.get("gasto_promedio_mensual"):
            sup["gasto_pc_mxn_anual"] = float(tam_overrides["gasto_promedio_mensual"]) * 12
            sup["fuente"] = "override del usuario sobre el supuesto TAM"
        if tam_overrides.get("f_nse") is not None:
            sup["f_nse"] = float(tam_overrides["f_nse"])
            sup["fuente"] = "override del usuario sobre el supuesto TAM"
        if tam_overrides.get("f_pen") is not None:
            sup["f_pen"] = float(tam_overrides["f_pen"])
            sup["fuente"] = "override del usuario sobre el supuesto TAM"
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
    # Efecto ancla (§3.12.3): A' = A × (1 + Σ w_a). Sin anclas detectadas
    # el atractivo no cambia (comportamiento histórico intacto).
    anclas = _anclas_cercanas(db, lat, lon)
    atractivo_efectivo = aplicar_efecto_ancla(atractivo_candidato, anclas)
    if anclas:
        advertencias.append(
            f"Efecto ancla aplicado en Huff: {len(anclas)} ancla(s) "
            f"cercana(s), atractividad ×{atractivo_efectivo / atractivo_candidato:.2f}"
            if atractivo_candidato else
            f"Efecto ancla: {len(anclas)} ancla(s) cercana(s) detectada(s)"
        )

    dist_candidato_km = 0.2  # consumidor representativo a 200 m del punto
    competidores = [(float(a or 0.5), max(float(dm) / 1000.0, 0.05)) for a, dm in comp]
    cuota = p_ij(atractivo_efectivo, dist_candidato_km, competidores, alpha=1.0, lambda_=lambda_giro)
    cuota_rango = p_ij_rango(atractivo_efectivo, dist_candidato_km, competidores, alpha=1.0, lambda_=lambda_giro)
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
            "atractivo_base": atractivo_candidato,
            "atractivo_efectivo": round(atractivo_efectivo, 4),
            "multiplicador_ancla": round(
                atractivo_efectivo / atractivo_candidato, 4
            ) if atractivo_candidato else 1.0,
        },
        "anclas": anclas,
        "veredicto": veredicto, "confianza": confianza, "factores": factores,
        "advertencias": advertencias,
    }


@router.post("/location", response_model=LocationAnalysisResponse)
def location_analysis(body: LocationAnalysisRequest, db: Session = Depends(get_db)):
    """Análisis de viabilidad de ubicación (CU-2): ISM por anillo, TAM y Huff."""
    overrides = {
        k: v for k, v in {
            "gasto_promedio_mensual": body.gasto_promedio_mensual,
            "f_nse": body.f_nse, "f_pen": body.f_pen,
        }.items() if v is not None
    }
    r = compute_location_analysis(
        db, body.giro, body.scian, body.lat, body.lon, body.radios,
        tam_overrides=overrides or None,
    )
    return LocationAnalysisResponse(
        giro=r["giro"], scian=r["scian"], lat=r["lat"], lon=r["lon"],
        anillos=[RingResult(**a) for a in r["anillos"]],
        tam_mxn=r["tam_mxn"], tam_rango_mxn=r["tam_rango"],
        huff_cuota_punto=r["huff"]["cuota_punto"],
        veredicto=r["veredicto"], factores=r["factores"],
        advertencias=r["advertencias"], lineage=lineage(db),
    )


def _item_desde_resultado(
    id_: str, nombre: str, territorio: str,
    lat: float, lon: float, resultado: dict,
) -> CompareItem:
    """CompareItem desde un resultado de compute_location_analysis."""
    anillos = resultado.get("anillos") or []
    anillo_mayor = anillos[-1] if anillos else {}
    return CompareItem(
        id=id_, nombre=nombre, territorio=territorio,
        center_lat=lat, center_lon=lon,
        veredicto=resultado["veredicto"],
        ism=float(anillo_mayor.get("ism", 0.0)),
        competencia=int(anillo_mayor.get("competencia", 0)),
        poblacion=float(anillo_mayor.get("demanda_pob_30_59", 0.0)),
        tam=float(resultado["tam_mxn"]),
        huff_score=float(resultado["huff"]["cuota_punto"]),
    )


def _item_investigacion(db: Session, investigation_id) -> CompareItem:
    """CompareItem recalculando el análisis de una investigación guardada."""
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
    return _item_desde_resultado(
        str(getattr(inv, "investigation_id", investigation_id)),
        inv.title, inv.territory_kind,
        float(inv.center_lat), float(inv.center_lon), resultado,
    )


@router.post("/compare", response_model=CompareResponse)
def comparar_investigaciones(body: CompareRequest, db: Session = Depends(get_db)):
    """Compara ubicaciones recalculando su análisis (ISM/TAM/Huff).

    Formas de entrada (ver ``CompareRequest``):

    - ``items`` (nueva, 2 a 6): investigaciones por ``investigation_id``
      y/o **puntos directos** ``{lat, lon, giro?, scian?, etiqueta?}`` que
      se calculan con el motor sin persistir investigación.
    - ``investigation_ids`` (legacy, 2 a 5): solo investigaciones.

    El resumen de cada item toma ISM, competencia y población del anillo
    de mayor radio.
    """
    items: list[CompareItem] = []
    if body.items:
        for entrada in body.items:
            if entrada.investigation_id is not None:
                items.append(_item_investigacion(db, entrada.investigation_id))
                continue
            if entrada.lat is None or entrada.lon is None:
                raise HTTPException(
                    status_code=422,
                    detail="Cada item del comparador necesita "
                           "investigation_id o {lat, lon}",
                )
            resultado = compute_location_analysis(
                db,
                giro=entrada.giro,
                scian=entrada.scian,
                lat=float(entrada.lat),
                lon=float(entrada.lon),
                radios=[1000, 2000],
            )
            items.append(_item_desde_resultado(
                f"punto:{entrada.lat:.5f},{entrada.lon:.5f}",
                entrada.etiqueta or entrada.giro
                or f"Punto {entrada.lat:.5f}, {entrada.lon:.5f}",
                "punto_directo",
                float(entrada.lat), float(entrada.lon), resultado,
            ))
        return CompareResponse(items=items, lineage=lineage(db))
    if body.investigation_ids:
        for investigation_id in body.investigation_ids:
            items.append(_item_investigacion(db, investigation_id))
        return CompareResponse(items=items, lineage=lineage(db))
    raise HTTPException(
        status_code=422,
        detail="Se requiere `items` (2 a 6) o `investigation_ids` (2 a 5)",
    )


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
