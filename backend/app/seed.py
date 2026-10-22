"""Datos de muestra deterministas para desarrollo (``python -m app.seed``).

Crea todo lo necesario: esquema ``prod``, tablas, las 32 particiones del
DENUE y los datos semilla (Roma-Condesa, CDMX). Idempotente: re-ejecutar
reemplaza los datos de la edición semilla.
"""
from __future__ import annotations

import json
import logging
import random
import sys

SEED = 42
EDITION = "DENUE_SEED_2026"
SOURCE_CODE = "DENUE"

log = logging.getLogger("geis.seed")

CAFETERIAS = [
    "Café Toscano", "Café Roma Norte", "La Esquina del Café", "Café Barajas",
    "Expendio de Café La Condesa", "Café Girasol", "Drip Café Roma",
    "Café Paraíso", "Tostaduría Insurgentes", "Café El Jarocho",
    "Brew Bar Condesa", "Café San Rafael", "La Tostadora Roma",
    "Café Nómada", "Espresso Hidalgo",
]
TORTILLERIAS = [
    "Tortillería La Guadalupana", "Tortillas Doña Mary", "Tortillería El Molino",
    "La Tortilla de Oro", "Tortillería San Cosme", "Tortillas La Palma",
    "El Comal de Oro", "Tortillería Los Volcanes", "Tortillas Lupita",
    "Molino La Rosa", "Tortillería El Faro", "La Milpa Dorada",
    "Tortillas El Sol",
]
TALLERES = [
    "Taller Hernández", "Auto Servicio Condesa", "Taller El Pistón",
    "Mecánica Roma", "Taller Los Hermanos", "Servicio Automotriz Insurgentes",
    "Taller El Rayo", "Refacciones y Taller Goma", "Taller Don Beto",
    "Mofles y Frenos Roma", "Taller 2000", "Auto Eléctrico Condesa",
]

ESTRATOS = [
    (1, "0 a 5"), (2, "6 a 10"), (3, "11 a 30"), (4, "31 a 50"),
    (5, "51 a 100"), (6, "101 a 250"), (7, "251 y más"),
]

SCIAN_SEED = [
    # (codigo, descripcion, sector, thermal_intensity, base_attractiveness, lambda)
    ("722515", "Servicios de preparación de café (cafeterías)", "72", 0.25, 0.70, 2.50),
    ("311830", "Elaboración de tortillas de maíz y molienda de nixtamal", "31", 0.85, 0.50, 3.00),
    ("811111", "Reparación mecánica de automóviles y camiones", "81", 0.45, 0.50, 2.50),
    ("311812", "Panificación industrial", "31", 0.90, 0.55, 2.80),
    ("325110", "Fabricación de petroquímicos básicos del gas natural", "32", 0.95, 0.40, 1.50),
    ("331110", "Industria básica del hierro y del acero", "33", 0.70, 0.40, 1.50),
    ("484122", "Autotransporte foráneo de carga general", "48", 0.50, 0.45, 1.80),
    ("313210", "Fabricación de telas anchas de tejido de trama", "31", 0.60, 0.40, 2.00),
    ("722511", "Restaurantes con servicio de preparación de alimentos", "72", 0.40, 0.65, 2.20),
    ("461110", "Comercio al por menor en tiendas de abarrotes", "46", 0.20, 0.60, 3.00),
]

AGEBS = [
    # (cvegeo, nombre, lat_c, lon_c, pob_total, pob_30_59, viv, pct_internet, nse_banda)
    ("090330001001", "Roma Norte", 19.4190, -99.1610, 8200, 3280, 3400, 91.5, "Alto"),
    ("090330001002", "Roma Sur", 19.4080, -99.1640, 6500, 2470, 2600, 88.2, "Alto"),
    ("090160001001", "Condesa", 19.4120, -99.1730, 9100, 3640, 3900, 93.1, "Alto"),
    ("090330001003", "Hipódromo", 19.4050, -99.1680, 4800, 1728, 1900, 85.4, "Medio a medio alto"),
]


def _square_wkt(lat_c: float, lon_c: float, half: float = 0.004) -> str:
    x0, x1 = lon_c - half, lon_c + half
    y0, y1 = lat_c - half, lat_c + half
    return f"POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))"


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    rng = random.Random(SEED)

    from sqlalchemy import text

    from app.db.base import Base
    from app.db.session import engine
    # Importa los modelos para registrarlos en Base.metadata.
    import app.models  # noqa: F401
    from app.models import CatScian, DataEdition, DataSource, InegiAgeb, ModelParam
    from app.models.denue import DenueEstablishment
    from geoalchemy2 import WKTElement

    log.info("Conectando a la BD...")
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS prod"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS stg"))
    Base.metadata.create_all(engine, checkfirst=True)
    log.info("Tablas verificadas/creadas")

    with engine.begin() as conn:
        for i in range(1, 33):
            e = f"{i:02d}"
            conn.execute(text(
                f"CREATE TABLE IF NOT EXISTS prod.denue_est_p{e} "
                f"PARTITION OF prod.denue_establishments FOR VALUES IN ('{e}')"
            ))
    log.info("32 particiones del DENUE verificadas")

    from app.db.session import SessionLocal
    session = SessionLocal()
    try:
        # ── Fuente y edición ──────────────────────────────────────────
        source = session.query(DataSource).filter_by(code=SOURCE_CODE).one_or_none()
        if source is None:
            source = DataSource(
                code=SOURCE_CODE,
                name="Directorio Estadístico Nacional de Unidades Económicas",
                provider="INEGI",
                license="Libre uso",
                url="https://www.inegi.org.mx/app/mapa/denue/",
            )
            session.add(source)
            session.flush()
        edition = session.query(DataEdition).filter_by(
            source_id=source.source_id, edition=EDITION).one_or_none()
        if edition is None:
            edition = DataEdition(
                source_id=source.source_id, edition=EDITION,
                notes="Edición semilla determinista (seed=42) para desarrollo",
            )
            session.add(edition)
            session.flush()
        # Limpieza idempotente de la edición semilla.
        session.query(DenueEstablishment).filter_by(edition_id=edition.edition_id).delete()
        session.query(InegiAgeb).filter_by(edition_id=edition.edition_id).delete()
        session.flush()

        # ── Catálogo SCIAN ────────────────────────────────────────────
        for codigo, desc, sector, thermal, attr, lam in SCIAN_SEED:
            row = session.get(CatScian, codigo)
            if row is None:
                session.add(CatScian(
                    scian_code=codigo, description=desc, sector_code=sector,
                    thermal_intensity=thermal, base_attractiveness=attr,
                    lambda_default=lam,
                ))
            else:
                row.description, row.sector_code = desc, sector
                row.thermal_intensity, row.base_attractiveness = thermal, attr
                row.lambda_default = lam

        # ── Parámetros de modelos ─────────────────────────────────────
        for vertical, model, params in [
            ("climatizacion", "IDT",
             {"w1": 0.35, "w2": 0.30, "w3": 0.20, "w4": 0.15,
              "descripcion": "Pesos por defecto §3.4"}),
            ("climatizacion", "SCORE_B2B",
             {"idt": 0.40, "tamano": 0.20, "accesibilidad": 0.15,
              "densidad": 0.15, "contacto": 0.10,
              "descripcion": "Pesos por defecto §3.5"}),
        ]:
            existe = session.query(ModelParam).filter_by(
                vertical=vertical, model=model, version=1).one_or_none()
            if existe is None:
                session.add(ModelParam(vertical=vertical, model=model,
                                       params=params, version=1, is_active=True))

        # ── AGEB ──────────────────────────────────────────────────────
        for cvegeo, nombre, lat_c, lon_c, pob, pob3059, viv, pct_net, nse in AGEBS:
            session.add(InegiAgeb(
                cvegeo=cvegeo, cve_ent="09", cve_mun=cvegeo[2:5],
                cve_loc="0001", cve_ageb=cvegeo[-4:], ambito="Urbana",
                pob_total=pob, pob_femenina=pob // 2, pob_masculina=pob - pob // 2,
                pob_0_14=int(pob * 0.15), pob_15_29=int(pob * 0.22),
                pob_30_59=pob3059, pob_60_mas=int(pob * 0.16),
                pob_sin_clasificar=pob - int(pob * 0.15) - int(pob * 0.22) - pob3059 - int(pob * 0.16),
                pea_ocupada=int(pob * 0.45), viv_habitadas=viv,
                prom_ocupantes_viv=round(pob / viv, 2),
                pct_viv_internet=pct_net, pct_viv_computadora=round(pct_net - 8, 2),
                pct_viv_automovil=round(pct_net - 35, 2), pct_viv_celular=round(pct_net + 4, 2),
                nse_score=0.82 if nse == "Alto" else 0.64, nse_banda=nse,
                geom=WKTElement(_square_wkt(lat_c, lon_c), srid=4326),
                edition_id=edition.edition_id,
            ))

        # ── Establecimientos (~40) ────────────────────────────────────
        fichas = ([(n, "722515") for n in CAFETERIAS]
                  + [(n, "311830") for n in TORTILLERIAS]
                  + [(n, "811111") for n in TALLERES])
        # Estratos: mayoría pequeños; algunos medianos/grandes para el IDT.
        estratos_plan = [1] * 14 + [2] * 10 + [3] * 8 + [4] * 4 + [5] * 2 + [6] * 1 + [7] * 1
        rng.shuffle(estratos_plan)

        colonias = ["Roma Norte", "Roma Sur", "Hipódromo Condesa", "Condesa"]
        for i, (nombre, scian) in enumerate(fichas):
            ord_e, txt_e = ESTRATOS[estratos_plan[i % len(estratos_plan)] - 1]
            lat = round(rng.uniform(19.405, 19.420), 6)
            lon = round(rng.uniform(-99.175, -99.155), 6)
            con_telefono = rng.random() < 0.7
            session.add(DenueEstablishment(
                denue_id=f"SEED09-{i:05d}", clee=None, nombre=nombre,
                scian_code=scian,
                scian_desc=next(d for c, d, *_ in SCIAN_SEED if c == scian),
                estrato_texto=txt_e, estrato_ordinal=ord_e,
                tipo_vialidad="Calle", nom_vialidad="Insurgentes Sur",
                num_exterior=str(rng.randint(10, 999)),
                colonia=rng.choice(colonias), cp="06700",
                cve_ent="09", entidad="Ciudad de México",
                cve_mun="033", municipio="Cuauhtémoc",
                cve_ageb=rng.choice([a[0] for a in AGEBS]),
                telefono=f"555{1000000 + rng.randint(0, 8999999)}" if con_telefono else None,
                correo=None, sitio_web=None,
                tipo_unidad="Única", tipo_establecimiento="Fijo",
                lat=lat, lon=lon,
                geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                edition_id=edition.edition_id, is_active=True,
            ))

        edition.records_total = len(fichas)
        edition.records_valid = len(fichas)
        edition.records_quarantine = 0

        # ── Módulo Radar (fusión GEIS × Biokool) ──────────────────────
        seed_radar(session)

        session.commit()
        log.info("Seed completado: %d establecimientos, %d AGEB, %d clases SCIAN",
                 len(fichas), len(AGEBS), len(SCIAN_SEED))
    finally:
        session.close()


# ---------------------------------------------------------------- fusión Radar
# Datos de muestra del módulo Radar (12 leads curadas, señales, providers,
# 1 run). Idempotente: INSERT ... ON CONFLICT DO NOTHING y checks previos.

#: (nombre, giro, ciudad, lon, lat, temp_zona, linea, etapa, score_inputs)
_LEADS_RADAR = [
    # 4 × nuevo
    ("Gasolinera El Faro del Norte", "Gasolinera", "Mexicali", -115.47, 32.62,
     38.5, "solar", "nuevo",
     {"idt": 0.85, "tamano": 0.43, "acceso": 0.9, "densidad": 0.6, "contacto": 0.67,
      "senal": True, "linkedin": 0.4}),
    ("Estacionamiento Central Juárez", "Estacionamiento público", "Hermosillo", -110.95, 29.07,
     35.8, "solar", "nuevo",
     {"idt": 0.70, "tamano": 0.29, "acceso": 0.8, "densidad": 0.5, "contacto": 0.33,
      "senal": False, "linkedin": 0.0}),
    ("Fábrica de Alimentos La Costeña del Sur", "Fábrica de alimentos", "Ciudad de México", -99.16, 19.42,
     24.1, "evaporativa", "nuevo",
     {"idt": 0.92, "tamano": 0.71, "acceso": 0.6, "densidad": 0.7, "contacto": 1.0,
      "senal": False, "linkedin": 0.2}),
    ("Hotel Brisas del Caribe Mexicano", "Hotel", "Mérida", -89.62, 20.97,
     29.8, "koolkat", "nuevo",
     {"idt": 0.65, "tamano": 0.57, "acceso": 0.7, "densidad": 0.8, "contacto": 0.67,
      "senal": True, "linkedin": 0.6}),
    # 3 × contactado
    ("Plaza Comercial Andares del Valle", "Plaza comercial", "Guadalajara", -103.35, 20.67,
     26.4, "evaporativa", "contactado",
     {"idt": 0.78, "tamano": 0.86, "acceso": 0.9, "densidad": 0.9, "contacto": 1.0,
      "senal": False, "linkedin": 0.3}),
    ("Gasolinera La Herradura Express", "Gasolinera", "Monterrey", -100.31, 25.67,
     28.9, "solar", "contactado",
     {"idt": 0.72, "tamano": 0.29, "acceso": 0.85, "densidad": 0.55, "contacto": 0.67,
      "senal": True, "linkedin": 0.5}),
    ("Restaurante Los Farolitos del Golfo", "Restaurante", "Villahermosa", -92.93, 17.99,
     29.5, "koolkat", "contactado",
     {"idt": 0.55, "tamano": 0.43, "acceso": 0.5, "densidad": 0.6, "contacto": 0.33,
      "senal": False, "linkedin": 0.1}),
    # 2 × reunion
    ("Corporativo Torre Diamante", "Oficinas corporativas", "Puebla", -98.20, 19.04,
     23.5, "evaporativa", "reunion",
     {"idt": 0.68, "tamano": 0.86, "acceso": 0.75, "densidad": 0.7, "contacto": 1.0,
      "senal": True, "linkedin": 0.8}),
    ("Hotel Paraíso Azul Riviera", "Hotel", "Cancún", -86.85, 21.16,
     28.9, "koolkat", "reunion",
     {"idt": 0.74, "tamano": 0.71, "acceso": 0.8, "densidad": 0.85, "contacto": 0.67,
      "senal": False, "linkedin": 0.4}),
    # 1 × propuesta
    ("Plaza Comercial Galerías del Mar", "Plaza comercial", "Tijuana", -117.02, 32.51,
     24.8, "solar", "propuesta",
     {"idt": 0.81, "tamano": 1.0, "acceso": 0.9, "densidad": 0.75, "contacto": 1.0,
      "senal": True, "linkedin": 0.7}),
    # 1 × ganado
    ("Planta Industrial Aceros del Bajío", "Planta industrial", "Querétaro", -100.39, 20.59,
     26.9, "evaporativa", "ganado",
     {"idt": 0.95, "tamano": 1.0, "acceso": 0.95, "densidad": 0.5, "contacto": 1.0,
      "senal": True, "linkedin": 0.9}),
    # 1 × perdido
    ("Taller Mecánico El Pistón Veloz", "Taller mecánico", "León", -101.68, 21.12,
     27.3, "koolkat", "perdido",
     {"idt": 0.35, "tamano": 0.14, "acceso": 0.4, "densidad": 0.3, "contacto": 0.0,
      "senal": False, "linkedin": 0.0}),
]

_PROVIDERS_RADAR = [
    # (name, kind, mode, provider)
    ("scraper", "scrape", "local", "local"),
    ("enrichment", "enrich", "local", "local"),
    ("crm", "crm", "disabled", "local"),
    ("email", "email", "disabled", "local"),
    ("weather", "weather", "local", "local"),
    ("linkedin", "signals", "cloud", "linkedin"),
    ("geocoding", "geocode", "local", "local"),
    ("routing", "route", "local", "local"),
]

_WARM_SIGNALS = [
    ("linkedin", "Pico de engagement en la página",
     "Los posts de la semana superaron 3× el promedio de interacciones.",
     "Hotel Paraíso Azul Riviera"),
    ("manual", "Contacto en expo industrial",
     "El gerente de planta pidió cotización de climatización evaporativa.",
     "Planta Industrial Aceros del Bajío"),
]


def seed_radar(session) -> None:
    """Siembra los datos de muestra del módulo Radar (idempotente).

    12 leads curadas con etapas/lineas variadas y temp_zona realista por
    ciudad, 2 warm_signals, providers iniciales y 1 run radar-01 en 'ok'.
    """
    from sqlalchemy import text

    from app.analytics.scoring_unificado import score_unificado

    # ── Leads curadas ─────────────────────────────────────────────
    for (nombre, giro, ciudad, lon, lat, temp, linea, etapa,
         inputs) in _LEADS_RADAR:
        comp = dict(inputs)
        comp["temp_zona"] = temp
        r = score_unificado(comp, vertical="biokool")
        session.execute(
            text(
                "INSERT INTO prod.leads "
                "(source, nombre, giro, direccion, geom, telefono, web, "
                " score, score_components, linea_recomendada, etapa, temp_zona, notas) "
                "VALUES ('manual', :nombre, :giro, :direccion, "
                " ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), "
                " :telefono, :web, :score, CAST(:comps AS jsonb), "
                " :linea, :etapa, :temp, :notas) "
                "ON CONFLICT (source, nombre, direccion) DO NOTHING"
            ),
            {
                "nombre": nombre,
                "giro": giro,
                "direccion": f"{ciudad}, México",
                "lon": lon,
                "lat": lat,
                "telefono": "5551234567",
                "web": None,
                "score": r["score"],
                "comps": json.dumps({
                    "x": r["x"], "desglose": r["desglose"],
                    "vertical": r["vertical"],
                }),
                "linea": linea,
                "etapa": etapa,
                "temp": temp,
                "notas": "Lead de muestra del módulo Radar.",
            },
        )

    # ── Warm signals ──────────────────────────────────────────────
    for fuente, titulo, detalle, empresa in _WARM_SIGNALS:
        existe = session.execute(
            text("SELECT 1 FROM prod.warm_signals WHERE titulo = :t LIMIT 1"),
            {"t": titulo},
        ).first()
        if existe is None:
            session.execute(
                text(
                    "INSERT INTO prod.warm_signals (fuente, titulo, detalle, empresa_ref) "
                    "VALUES (:fuente, :titulo, :detalle, :empresa)"
                ),
                {"fuente": fuente, "titulo": titulo,
                 "detalle": detalle, "empresa": empresa},
            )

    # ── Providers ─────────────────────────────────────────────────
    for name, kind, mode, provider in _PROVIDERS_RADAR:
        session.execute(
            text(
                "INSERT INTO prod.providers (name, kind, mode, provider, config, enabled) "
                "VALUES (:name, :kind, :mode, :provider, '{}', :enabled) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {"name": name, "kind": kind, "mode": mode,
             "provider": provider, "enabled": mode != "disabled"},
        )

    # ── Run radar-01 ok ───────────────────────────────────────────
    existe = session.execute(
        text("SELECT 1 FROM prod.runs WHERE pipeline = 'radar-01' LIMIT 1")
    ).first()
    if existe is None:
        session.execute(
            text(
                "INSERT INTO prod.runs (pipeline, estado, detalle, started_at, finished_at) "
                "VALUES ('radar-01', 'ok', "
                " CAST(:detalle AS jsonb), now() - interval '1 hour', now())"
            ),
            {"detalle": json.dumps(
                {"origen": "seed", "nota": "Corrida de muestra del pipeline radar-01"})},
        )

    log.info("Seed Radar: %d leads, %d señales, %d providers, 1 run",
             len(_LEADS_RADAR), len(_WARM_SIGNALS), len(_PROVIDERS_RADAR))


if __name__ == "__main__":
    sys.exit(run())
