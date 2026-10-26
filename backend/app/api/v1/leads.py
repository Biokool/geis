"""Router de leads: tabla CRM con paginación por cursor.

Incluye el listado DENUE original (GET "") más las leads curadas del
módulo Radar (GET /curados, GET /curados/{id}, PATCH /curados/{id})
sobre ``prod.leads``, y la exportación a CSV (POST /export).
"""
import base64
import csv
import io
import json
import re
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics import b2b_score, completitud_contacto, e_estrato, idt
from app.api.v1._common import lineage
from app.api.v1.analysis import CLIMA_DEFAULT, _intensidad_scian
from app.db.session import get_db, safe_rollback
from app.schemas.leads import LeadOut, LeadsPage
from app.schemas.radar import (
    EnrichGeoDetalle,
    EnrichGeoIn,
    EnrichGeoOut,
    Etapa,
    LeadCountOut,
    LeadUpdate,
    LeadsCuradosPage,
)
from app.schemas.radar import LeadOut as LeadCuradoOut

router = APIRouter(prefix="/leads", tags=["leads"])


def _encode_cursor(denue_id: str) -> str:
    return base64.urlsafe_b64encode(json.dumps({"last": denue_id}).encode()).decode()


def _decode_cursor(cursor: str | None) -> str | None:
    if not cursor:
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode()).get("last")
    except Exception:
        return None


@router.get("", response_model=LeadsPage)
def listar_leads(
    cursor: str | None = Query(default=None, description="Cursor opaco de paginación"),
    limit: int = Query(default=20, ge=1, le=100),
    estrato_min: int | None = Query(default=None, ge=1, le=7),
    scian: list[str] | None = Query(default=None),
    entidad: str | None = Query(default=None, description="Filtra por entidad (DENUE)"),
    municipio: str | None = Query(default=None, description="Filtra por municipio (DENUE)"),
    colonia: str | None = Query(default=None, description="Filtra por colonia (DENUE)"),
    cp: str | None = Query(default=None, description="Filtra por código postal (DENUE)"),
    db: Session = Depends(get_db),
):
    """Lista leads (establecimientos) con IDT/score calculados, paginación por cursor.

    Es también la capa DENUE del mapa: acepta los filtros geográficos
    (entidad, municipio, colonia, cp y scian vía ``scian``) sobre las
    columnas que ``prod.denue_establishments`` ya trae.
    """
    last = _decode_cursor(cursor)
    filtros = ["is_active"]
    params: dict = {"limit": limit + 1}
    if estrato_min:
        filtros.append("estrato_ordinal >= :estrato_min")
        params["estrato_min"] = estrato_min
    if scian:
        filtros.append("scian_code = ANY(:scians)")
        params["scians"] = scian
    if entidad:
        filtros.append("entidad = :entidad")
        params["entidad"] = entidad
    if municipio:
        filtros.append("municipio = :municipio")
        params["municipio"] = municipio
    if colonia:
        filtros.append("colonia = :colonia")
        params["colonia"] = colonia
    if cp:
        filtros.append("cp = :cp")
        params["cp"] = cp
    if last:
        filtros.append("denue_id > :last")
        params["last"] = last

    filas = db.execute(
        text(
            "SELECT denue_id, nombre, scian_code, scian_desc, estrato_texto, "
            "estrato_ordinal, colonia, municipio, telefono, correo, sitio_web, "
            "lat, lon, entidad, cp FROM prod.denue_establishments "
            f"WHERE {' AND '.join(filtros)} ORDER BY denue_id LIMIT :limit"
        ),
        params,
    ).all()

    items: list[LeadOut] = []
    for f in filas[:limit]:
        (denue_id, nombre, scian_code, scian_desc, estrato_txt, estrato_ord,
         colonia, municipio, tel, correo, sitio, lat, lon, entidad_v, cp_v) = f
        r_idt = idt(int(estrato_ord), _intensidad_scian(db, scian_code), CLIMA_DEFAULT, None)
        s = b2b_score({
            "idt": r_idt["idt"] / 100.0,
            "tamano": e_estrato(int(estrato_ord)),
            "accesibilidad": 0.5,  # sin corredor de referencia en este listado
            "densidad": 0.5,
            "contacto": completitud_contacto(bool(tel), bool(correo), bool(sitio)),
        })
        items.append(LeadOut(
            denue_id=denue_id, nombre=nombre, scian_code=scian_code,
            scian_desc=scian_desc, estrato_texto=estrato_txt,
            estrato_ordinal=int(estrato_ord), colonia=colonia, municipio=municipio,
            entidad=entidad_v, cp=cp_v,
            telefono=tel, correo=correo, sitio_web=sitio,
            lat=float(lat), lon=float(lon),
            idt=r_idt["idt"], score=s["score"],
        ))

    next_cursor = _encode_cursor(filas[limit - 1][0]) if len(filas) > limit else None
    return LeadsPage(items=items, next_cursor=next_cursor, limit=limit, lineage=lineage(db))


# ------------------------------------------------- exportación CSV
_COLUMNAS_CSV = (
    "denue_id", "nombre", "scian_code", "scian_desc", "estrato_texto",
    "municipio", "telefono", "correo", "sitio_web", "lat", "lon", "idt", "score",
)


def filas_a_csv(filas, intensidades: dict[str, float]) -> str:
    """Convierte filas de ``prod.denue_establishments`` a CSV con IDT y score.

    Función pura (testeable sin BD). Cada fila es la tupla
    (denue_id, nombre, scian_code, scian_desc, estrato_texto, estrato_ordinal,
    municipio, telefono, correo, sitio_web, lat, lon). ``intensidades`` mapea
    scian_code → intensidad térmica (0–1); sin entrada se usa 0.5.
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_COLUMNAS_CSV)
    for f in filas:
        (denue_id, nombre, scian_code, scian_desc, estrato_txt, estrato_ord,
         municipio, tel, correo, sitio, lat, lon) = f
        try:
            r_idt = idt(int(estrato_ord), intensidades.get(scian_code, 0.5),
                        CLIMA_DEFAULT, None)
            s = b2b_score({
                "idt": r_idt["idt"] / 100.0,
                "tamano": e_estrato(int(estrato_ord)),
                "accesibilidad": 0.5,  # sin corredor de referencia en este listado
                "densidad": 0.5,
                "contacto": completitud_contacto(bool(tel), bool(correo), bool(sitio)),
            })
            idt_v, score_v = r_idt["idt"], s["score"]
        except (ValueError, TypeError):
            # Fila con datos inválidos: se exporta sin score en lugar de
            # tumbar la exportación completa.
            idt_v, score_v = None, None
        w.writerow([denue_id, nombre, scian_code, scian_desc, estrato_txt,
                    municipio, tel, correo, sitio, lat, lon, idt_v, score_v])
    return buf.getvalue()


@router.post("/export")
def exportar_leads(
    formato: str = Query(default="csv", description="Formato de exportación"),
    db: Session = Depends(get_db),
):
    """Exporta leads (establecimientos) con IDT y score calculados.

    ``formato=csv`` genera el archivo (límite 5,000 filas). Excel aún no
    está disponible: responde 501 honesto en lugar de un 404.
    """
    if formato == "excel":
        raise HTTPException(
            status_code=501,
            detail="Excel no disponible en esta versión; usa formato=csv",
        )
    if formato != "csv":
        raise HTTPException(
            status_code=422, detail="formato debe ser 'csv'"
        )
    intensidades = {
        r[0]: float(r[1])
        for r in db.execute(
            text("SELECT scian_code, thermal_intensity FROM prod.cat_scian")
        ).all()
    }
    filas = db.execute(
        text(
            "SELECT denue_id, nombre, scian_code, scian_desc, estrato_texto, "
            "estrato_ordinal, municipio, telefono, correo, sitio_web, lat, lon "
            "FROM prod.denue_establishments WHERE is_active "
            "ORDER BY denue_id LIMIT 5000"
        )
    ).all()
    contenido = filas_a_csv(filas, intensidades)
    return StreamingResponse(
        iter([contenido]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


# ------------------------------------------------- leads curadas (Radar)
_COLUMNAS_CURADO = (
    "lead_id, source, nombre, giro, direccion, telefono, web, rating, "
    "score, score_components, linea_recomendada, etapa, temp_zona, notas, "
    "enriquecido_apollo, crm_synced_at, created_at, updated_at, "
    "ST_Y(geom) AS lat, ST_X(geom) AS lon, "
    "entidad, municipio, colonia, cp, scian"
)


def _fila_a_curado(f) -> LeadCuradoOut:
    """Mapea una fila SQL de prod.leads al esquema de salida."""
    return LeadCuradoOut(
        lead_id=f[0], source=f[1], nombre=f[2], giro=f[3], direccion=f[4],
        telefono=f[5], web=f[6],
        rating=float(f[7]) if f[7] is not None else None,
        score=float(f[8]) if f[8] is not None else None,
        score_components=f[9] or {},
        linea_recomendada=f[10], etapa=f[11],
        temp_zona=float(f[12]) if f[12] is not None else None,
        notas=f[13], enriquecido_apollo=bool(f[14]), crm_synced_at=f[15],
        lat=float(f[18]) if f[18] is not None else None,
        lon=float(f[19]) if f[19] is not None else None,
        created_at=f[16], updated_at=f[17],
        entidad=f[20], municipio=f[21], colonia=f[22], cp=f[23], scian=f[24],
    )


#: Campos geográficos filtrables de prod.leads (migración 0005). Los
#: nombres de columna son literales de código (nunca input del usuario);
#: los valores siempre viajan parametrizados.
_CAMPOS_GEO = ("entidad", "municipio", "colonia", "cp", "scian")


def _agregar_filtros_geo(filtros: list[str], params: dict, **valores) -> None:
    """Agrega condiciones AND ``campo = :geo_campo`` por cada valor dado."""
    for campo in _CAMPOS_GEO:
        valor = valores.get(campo)
        if valor:
            filtros.append(f"{campo} = :geo_{campo}")
            params[f"geo_{campo}"] = valor


def _encode_curado_cursor(lead_id: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"last": lead_id}).encode()).decode()


def _decode_curado_cursor(cursor: str | None) -> int | None:
    if not cursor:
        return None
    try:
        valor = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode()).get("last")
        return int(valor) if valor is not None else None
    except Exception:
        return None


@router.get("/count", response_model=LeadCountOut)
def contar_leads_curados(
    etapa: Etapa | None = Query(default=None, description="Filtra por etapa comercial"),
    linea: str | None = Query(default=None, description="Filtra por linea_recomendada"),
    source: str | None = Query(default=None, description="Filtra por origen"),
    entidad: str | None = Query(default=None, description="Filtra por entidad (geo derivada)"),
    municipio: str | None = Query(default=None, description="Filtra por municipio (geo derivada)"),
    colonia: str | None = Query(default=None, description="Filtra por colonia (geo derivada)"),
    cp: str | None = Query(default=None, description="Filtra por código postal (geo derivada)"),
    scian: str | None = Query(default=None, description="Filtra por clase SCIAN (geo derivada)"),
    db: Session = Depends(get_db),
):
    """Conteo total de leads curadas (prod.leads), sin paginación.

    Es el total del badge del menú y del KPI de Inicio. Acepta los mismos
    filtros que ``GET /leads/curados`` (etapa, linea, source y los 5
    geográficos: entidad, municipio, colonia, cp, scian), con WHERE
    dinámico parametrizado.
    """
    filtros: list[str] = []
    params: dict = {}
    if etapa:
        filtros.append("etapa = :etapa")
        params["etapa"] = etapa
    if linea:
        filtros.append("linea_recomendada = :linea")
        params["linea"] = linea
    if source:
        filtros.append("source = :source")
        params["source"] = source
    _agregar_filtros_geo(
        filtros, params,
        entidad=entidad, municipio=municipio, colonia=colonia, cp=cp,
        scian=scian,
    )

    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    total = db.execute(
        text(f"SELECT COUNT(*) FROM prod.leads {where}"),
        params,
    ).scalar()
    return LeadCountOut(total=int(total or 0))


@router.get("/curados", response_model=LeadsCuradosPage)
def listar_leads_curados(
    etapa: Etapa | None = Query(default=None, description="Filtra por etapa comercial"),
    linea: str | None = Query(default=None, description="Filtra por linea_recomendada"),
    source: str | None = Query(default=None, description="Filtra por origen"),
    entidad: str | None = Query(default=None, description="Filtra por entidad (geo derivada)"),
    municipio: str | None = Query(default=None, description="Filtra por municipio (geo derivada)"),
    colonia: str | None = Query(default=None, description="Filtra por colonia (geo derivada)"),
    cp: str | None = Query(default=None, description="Filtra por código postal (geo derivada)"),
    scian: str | None = Query(default=None, description="Filtra por clase SCIAN (geo derivada)"),
    cursor: str | None = Query(default=None, description="Cursor opaco de paginación"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Leads curadas (prod.leads) con paginación por cursor.

    Es el endpoint que alimenta la lista de Leads y la capa de leads del
    mapa (trae lat/lon): acepta los 5 filtros geográficos derivados
    (entidad, municipio, colonia, cp, scian) combinados en AND.
    """
    last = _decode_curado_cursor(cursor)
    filtros: list[str] = []
    params: dict = {"limit": limit + 1}
    if etapa:
        filtros.append("etapa = :etapa")
        params["etapa"] = etapa
    if linea:
        filtros.append("linea_recomendada = :linea")
        params["linea"] = linea
    if source:
        filtros.append("source = :source")
        params["source"] = source
    _agregar_filtros_geo(
        filtros, params,
        entidad=entidad, municipio=municipio, colonia=colonia, cp=cp,
        scian=scian,
    )
    if last is not None:
        filtros.append("lead_id > :last")
        params["last"] = last

    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    filas = db.execute(
        text(f"SELECT {_COLUMNAS_CURADO} FROM prod.leads {where} "
             "ORDER BY lead_id LIMIT :limit"),
        params,
    ).all()

    items = [_fila_a_curado(f) for f in filas[:limit]]
    next_cursor = _encode_curado_cursor(filas[limit - 1][0]) if len(filas) > limit else None
    return LeadsCuradosPage(items=items, next_cursor=next_cursor, limit=limit)


@router.get("/curados/{lead_id}", response_model=LeadCuradoOut)
def obtener_lead_curado(lead_id: int, db: Session = Depends(get_db)):
    """Detalle de una lead curada."""
    fila = db.execute(
        text(f"SELECT {_COLUMNAS_CURADO} FROM prod.leads WHERE lead_id = :lid"),
        {"lid": lead_id},
    ).first()
    if fila is None:
        raise HTTPException(status_code=404, detail=f"lead {lead_id} no encontrado")
    return _fila_a_curado(fila)


@router.patch("/curados/{lead_id}", response_model=LeadCuradoOut)
def actualizar_lead_curado(lead_id: int, payload: LeadUpdate, db: Session = Depends(get_db)):
    """Actualiza etapa y/o notas de una lead curada."""
    sets: list[str] = []
    params: dict = {"lid": lead_id}
    if payload.etapa is not None:
        sets.append("etapa = :etapa")
        params["etapa"] = payload.etapa
    if payload.notas is not None:
        sets.append("notas = :notas")
        params["notas"] = payload.notas
    if not sets:
        raise HTTPException(status_code=422, detail="nada que actualizar (etapa/notas)")
    sets.append("updated_at = :ahora")
    params["ahora"] = datetime.now().astimezone()

    res = db.execute(
        text(f"UPDATE prod.leads SET {', '.join(sets)} WHERE lead_id = :lid"),
        params,
    )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"lead {lead_id} no encontrado")
    db.commit()
    fila = db.execute(
        text(f"SELECT {_COLUMNAS_CURADO} FROM prod.leads WHERE lead_id = :lid"),
        {"lid": lead_id},
    ).first()
    # Auto-aprendizaje: una conversión ('ganado') alimenta knowledge_facts
    # con source='system'. try/except para no romper el flujo si falla.
    if payload.etapa == "ganado":
        try:
            from app.ai import knowledge as _knowledge
            from app.company import store as _store

            giro = fila[3] if fila is not None else None
            _knowledge.save_fact(
                db,
                _store.active_vertical_id(db),
                f"conversion:{giro or 'sin_giro'}",
                {
                    "lead_id": lead_id,
                    "nombre": fila[2] if fila is not None else None,
                    "giro": giro,
                    "score": float(fila[8])
                    if fila is not None and fila[8] is not None
                    else None,
                },
                source="system",
                confidence=1.0,
            )
        except Exception:
            safe_rollback(db)
    return _fila_a_curado(fila)


# --------------------------------------- enriquecimiento geográfico (0005)
#: Catálogo de entidades federativas por clave INEGI (cve_ent 01–32).
#: ``prod.inegi_agebs`` solo trae claves; el nombre sale de
#: ``prod.marco_entidades`` cuando existe y, si no, de este mapa.
ENTIDADES_POR_CVE: dict[str, str] = {
    "01": "Aguascalientes", "02": "Baja California",
    "03": "Baja California Sur", "04": "Campeche",
    "05": "Coahuila de Zaragoza", "06": "Colima", "07": "Chiapas",
    "08": "Chihuahua", "09": "Ciudad de México", "10": "Durango",
    "11": "Guanajuato", "12": "Guerrero", "13": "Hidalgo", "14": "Jalisco",
    "15": "México", "16": "Michoacán de Ocampo", "17": "Morelos",
    "18": "Nayarit", "19": "Nuevo León", "20": "Oaxaca", "21": "Puebla",
    "22": "Querétaro", "23": "Quintana Roo", "24": "San Luis Potosí",
    "25": "Sinaloa", "26": "Sonora", "27": "Tabasco", "28": "Tamaulipas",
    "29": "Tlaxcala", "30": "Veracruz de Ignacio de la Llave",
    "31": "Yucatán", "32": "Zacatecas",
}

#: Código postal mexicano: 5 dígitos como palabra completa en texto libre.
_RE_CP = re.compile(r"\b\d{5}\b")

#: Radio (metros) para buscar el establecimiento DENUE de referencia.
_RADIO_DENUE_M = 500

_SQL_CANDIDATOS_GEO = (
    "SELECT lead_id, direccion, ST_Y(geom) AS lat, ST_X(geom) AS lon, "
    "entidad, municipio, colonia, cp, scian FROM prod.leads "
    "WHERE entidad IS NULL OR municipio IS NULL OR colonia IS NULL "
    "OR cp IS NULL OR scian IS NULL "
    "ORDER BY lead_id LIMIT :limite"
)

# AGEB que contiene el punto del lead (ST_Intersects cubre también el
# punto sobre el borde del polígono). Nombres vía catálogos del Marco
# Geoestadístico; si falta el renglón del catálogo, llegan NULL y el
# llamador decide (entidad: mapa por clave; municipio: queda vacío).
_SQL_AGEB_DEL_LEAD = (
    "SELECT a.cve_ent, a.cve_mun, e.nom_ent, m.nom_mun "
    "FROM prod.inegi_agebs a "
    "JOIN prod.leads l ON l.lead_id = :lid AND ST_Intersects(a.geom, l.geom) "
    "LEFT JOIN prod.marco_entidades e ON e.cve_ent = a.cve_ent "
    "LEFT JOIN prod.marco_municipios m "
    "ON m.cve_ent = a.cve_ent AND m.cve_mun = a.cve_mun "
    "LIMIT 1"
)

# Establecimiento DENUE más cercano al lead (≤500 m). La columna SCIAN
# real del DENUE es ``scian_code`` (no ``clase_scian``). Entidad/municipio
# del DENUE sirven de respaldo cuando el AGEB o el catálogo del Marco no
# tienen el nombre (el ETL de marco_municipios aún es parcial).
_SQL_DENUE_CERCANO = (
    "SELECT d.entidad, d.municipio, d.colonia, d.cp, d.scian_code "
    "FROM prod.denue_establishments d "
    "JOIN prod.leads l ON l.lead_id = :lid "
    "WHERE d.is_active AND ST_DWithin(d.geom::geography, l.geom::geography, :radio) "
    "ORDER BY ST_Distance(d.geom::geography, l.geom::geography) ASC "
    "LIMIT 1"
)

# Idempotencia: COALESCE conserva lo ya llenado; solo se escribe en
# campos vacíos, así una segunda corrida no pisa datos existentes.
_SQL_UPDATE_GEO = (
    "UPDATE prod.leads SET "
    "entidad = COALESCE(entidad, :entidad), "
    "municipio = COALESCE(municipio, :municipio), "
    "colonia = COALESCE(colonia, :colonia), "
    "cp = COALESCE(cp, :cp), "
    "scian = COALESCE(scian, :scian), "
    "updated_at = now() "
    "WHERE lead_id = :lid"
)

_SQL_PENDIENTES_GEO = (
    "SELECT COUNT(*) FROM prod.leads "
    "WHERE entidad IS NULL OR municipio IS NULL OR colonia IS NULL "
    "OR cp IS NULL OR scian IS NULL"
)


def _cp_en_direccion(direccion: str | None) -> str | None:
    """Primer CP de 5 dígitos en la dirección de texto libre, o None."""
    if not direccion:
        return None
    m = _RE_CP.search(direccion)
    return m.group(0) if m else None


#: Abreviaturas de entidades federativas tal como aparecen en las
#: direcciones formateadas ("Qro.", "B.C.", "CDMX", ...). La clave es
#: el segmento normalizado: sin puntos, sin espacios, en mayúsculas.
_ABREV_ENTIDAD: dict[str, str] = {
    "AGS": "Aguascalientes", "BC": "Baja California",
    "BCS": "Baja California Sur", "CAMP": "Campeche",
    "COAH": "Coahuila de Zaragoza", "COL": "Colima",
    "CHIS": "Chiapas", "CHIH": "Chihuahua", "CDMX": "Ciudad de México",
    "DF": "Ciudad de México", "DGO": "Durango", "GTO": "Guanajuato",
    "GRO": "Guerrero", "HGO": "Hidalgo", "JAL": "Jalisco",
    "MICH": "Michoacán de Ocampo", "MOR": "Morelos",
    "NL": "Nuevo León", "NAY": "Nayarit", "OAX": "Oaxaca",
    "PUE": "Puebla", "QRO": "Querétaro", "QR": "Quintana Roo",
    "SLP": "San Luis Potosí", "SIN": "Sinaloa", "SON": "Sonora",
    "TAB": "Tabasco", "TAMPS": "Tamaulipas", "TLAX": "Tlaxcala",
    "VER": "Veracruz de Ignacio de la Llave", "YUC": "Yucatán",
    "ZAC": "Zacatecas", "MEX": "México", "EDOMEX": "México",
}

#: Nombres oficiales de entidad. Se excluye "México" a secas porque en
#: una dirección formateada es el país, no el estado de México.
_NOMBRE_ENTIDAD = frozenset(ENTIDADES_POR_CVE.values()) - {"México"}

#: Países que pueden cerrar la dirección y jamás son entidad/colonia.
_PAIS_EN_DIRECCION = frozenset(("mexico", "méxico"))


def _entidad_en_texto(segmento: str) -> str | None:
    """Entidad federativa si el segmento es su nombre o abreviatura."""
    limpio = segmento.strip()
    if not limpio:
        return None
    if limpio in _NOMBRE_ENTIDAD:
        return limpio
    clave = re.sub(r"[.\s]+", "", limpio).upper()
    return _ABREV_ENTIDAD.get(clave)


def _parsear_direccion_geo(direccion: str | None) -> dict[str, str | None]:
    """Geografía extraída del texto de la dirección (formato Google MX).

    Último recurso para leads sin cobertura de AGEB/DENUE/Marco: no
    inventa nada, solo lee lo que la propia dirección dice. Formato
    esperado: "Calle y número, Colonia, 76000 Municipio, Edo." — el
    segmento "CP Municipio" da cp y municipio (o la entidad, cuando es
    exactamente su nombre, p. ej. "06000 Ciudad de México"); el segmento
    posterior da la entidad por abreviatura ("Qro.") o nombre; la
    colonia es el segmento inmediato anterior al CP siempre que no sea
    la calle (primer segmento) ni contenga un CP.
    """
    geo: dict[str, str | None] = dict.fromkeys(("entidad", "municipio", "colonia", "cp"))
    if not direccion:
        return geo
    segmentos = [s.strip() for s in direccion.split(",") if s.strip()]
    if not segmentos:
        return geo
    idx_cp = None
    for i, seg in enumerate(segmentos):
        m = re.match(r"^(\d{5})\s+(.+)$", seg)
        if m:
            idx_cp = i
            geo["cp"] = m.group(1)
            resto = m.group(2).strip()
            entidad = _entidad_en_texto(resto)
            if entidad == resto:
                geo["entidad"] = entidad
            elif resto:
                geo["municipio"] = resto
            break
    if geo["entidad"] is None:
        rango = (
            range(idx_cp + 1, len(segmentos))
            if idx_cp is not None else range(len(segmentos))
        )
        for i in rango:
            if segmentos[i].lower() in _PAIS_EN_DIRECCION:
                continue
            entidad = _entidad_en_texto(segmentos[i])
            if entidad:
                geo["entidad"] = entidad
                break
    if idx_cp is not None and idx_cp >= 2:
        colonia = segmentos[idx_cp - 1]
        if (colonia.lower() not in _PAIS_EN_DIRECCION
                and not _RE_CP.search(colonia)):
            geo["colonia"] = colonia
    return geo


@router.post("/enrich-geo", response_model=EnrichGeoOut)
def enriquecer_geo(
    payload: EnrichGeoIn | None = Body(default=None),
    db: Session = Depends(get_db),
):
    """Deriva entidad/municipio/colonia/cp/scian para leads sin geografía.

    Para leads con geometría (``geom``): el AGEB que lo contiene da
    entidad y municipio (nombres de ``marco_entidades``/
    ``marco_municipios``; si el catálogo de entidades no trae el renglón,
    la entidad se mapea desde ``cve_ent`` con el catálogo 01–32 en
    código; si el municipio no tiene nombre en el catálogo, queda vacío)
    y el establecimiento DENUE más cercano (≤500 m) da colonia, cp y
    scian (``scian_code``). Para leads sin geometría (y como respaldo
    cuando AGEB/DENUE no cubren el punto, p. ej. Marco parcial) se
    parsea la dirección formateada (formato Google MX): CP, municipio,
    entidad por nombre/abreviatura y colonia del segmento previo al CP.

    Idempotente: nunca pisa un campo ya llenado (COALESCE en el UPDATE);
    reejecutar sin cambios nuevos reporta ``actualizados = 0``.
    ``pendientes`` = leads que tras la corrida aún tienen algún campo
    geo vacío (incluye los no procesados por ``limite``). En
    ``detalle``, ``solo_cp`` cuenta los leads sin geometría a los que la
    dirección sí dio algún dato (históricamente solo el CP) y
    ``sin_datos`` los que no dieron ninguno.
    """
    limite = payload.limite if payload else 500
    candidatos = db.execute(
        text(_SQL_CANDIDATOS_GEO), {"limite": limite}
    ).all()

    actualizados = 0
    detalle = EnrichGeoDetalle()
    for fila in candidatos:
        (lead_id, direccion, lat, lon,
         ent_act, mun_act, col_act, cp_act, scian_act) = fila
        actuales = {
            "entidad": ent_act, "municipio": mun_act, "colonia": col_act,
            "cp": cp_act, "scian": scian_act,
        }
        nuevos: dict[str, str | None] = dict.fromkeys(_CAMPOS_GEO)

        if lat is not None and lon is not None:
            detalle.con_geometria += 1
            ageb = db.execute(
                text(_SQL_AGEB_DEL_LEAD), {"lid": lead_id}
            ).first()
            if ageb is not None:
                cve_ent, _cve_mun, nom_ent, nom_mun = ageb
                nuevos["entidad"] = nom_ent or ENTIDADES_POR_CVE.get(cve_ent)
                nuevos["municipio"] = nom_mun
            denue = db.execute(
                text(_SQL_DENUE_CERCANO),
                {"lid": lead_id, "radio": _RADIO_DENUE_M},
            ).first()
            if denue is not None:
                d_ent, d_mun, d_col, d_cp, d_scian = denue
                # El AGEB/catálogo manda; el DENUE cercano rellena lo que
                # falte (colonia/CP/SCIAN de referencia y municipio cuando
                # marco_municipios no tiene el renglón).
                nuevos["entidad"] = nuevos["entidad"] or d_ent
                nuevos["municipio"] = nuevos["municipio"] or d_mun
                nuevos["colonia"] = d_col
                nuevos["cp"] = d_cp
                nuevos["scian"] = d_scian
            if not nuevos["cp"]:
                nuevos["cp"] = _cp_en_direccion(direccion)
            # Respaldo de texto: AGEB/DENUE/Marco no cubren todo el país
            # (los catálogos del Marco aún son parciales); la dirección
            # formateada sí dice municipio/entidad/colonia.
            del_texto = _parsear_direccion_geo(direccion)
            for campo in ("entidad", "municipio", "colonia", "cp"):
                nuevos[campo] = nuevos[campo] or del_texto[campo]
        else:
            del_texto = _parsear_direccion_geo(direccion)
            if any(del_texto.values()):
                detalle.solo_cp += 1
                nuevos.update(del_texto)
            else:
                detalle.sin_datos += 1

        # Solo cuentan/escriben los campos que estaban vacíos.
        cambios = {
            campo: valor
            for campo, valor in nuevos.items()
            if valor and not actuales[campo]
        }
        if cambios:
            params = {campo: cambios.get(campo) for campo in _CAMPOS_GEO}
            params["lid"] = lead_id
            db.execute(text(_SQL_UPDATE_GEO), params)
            actualizados += 1

    db.commit()
    pendientes = db.execute(text(_SQL_PENDIENTES_GEO)).scalar()
    return EnrichGeoOut(
        actualizados=actualizados,
        pendientes=int(pendientes or 0),
        detalle=detalle,
    )
