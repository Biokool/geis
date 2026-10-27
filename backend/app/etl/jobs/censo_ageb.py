"""Job ETL: ingesta del Censo 2020 a nivel AGEB urbana + geometrías del MG.

Cruza las variables sociodemográficas de ``censo_<ent>.zip`` con las AGEB
urbanas de ``mg_<ent>.zip`` (``<ent>a.shp``, LCC → WGS84) y carga
``prod.inegi_agebs``. Idempotente por (edición, entidad).

El bloque NSE es un proxy documentado (no es el índice AMAI oficial):
combina cobertura de Internet, computadora, automóvil y celular.

Uso:
    python -m app.etl.jobs.censo_ageb --edition CPV2020_AGEB_22 --edo 22
"""
from __future__ import annotations

import csv
import io
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from app.etl.jobs._common import base_parser, configurar_logging

SOURCE_CODE = "CPV2020"
DEFAULT_RAW_DIR = "/code/data/raw"
CHUNK = 500
AMBITO = "Urbana"

PESOS_NSE = {
    "internet": 0.35,
    "computadora": 0.25,
    "automovil": 0.25,
    "celular": 0.15,
}


def _int(val: object) -> int | None:
    try:
        return int(str(val).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _dec(val: object) -> float | None:
    try:
        return float(str(val).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _pct(num: int | None, den: int | None) -> float | None:
    if num is None or not den or den <= 0:
        return None
    return round(max(0.0, min(100.0, 100.0 * num / den)), 2)


def _nse(pcts: dict[str, float | None]) -> tuple[float | None, str | None]:
    disponibles = {k: v for k, v in pcts.items() if v is not None}
    if not disponibles:
        return None, None
    peso_total = sum(PESOS_NSE[k] for k in disponibles)
    score = sum(PESOS_NSE[k] * v for k, v in disponibles.items()) / peso_total / 100.0
    score = round(score, 3)
    if score >= 0.80:
        banda = "Alto"
    elif score >= 0.60:
        banda = "Medio a medio alto"
    elif score >= 0.45:
        banda = "Medio"
    elif score >= 0.30:
        banda = "Medio bajo"
    else:
        banda = "Bajo"
    return score, banda


def _ensure_fuente(session):
    from app.models import DataSource

    fuente = session.query(DataSource).filter_by(code=SOURCE_CODE).one_or_none()
    if fuente is None:
        fuente = DataSource(
            code=SOURCE_CODE,
            name="Censo de Población y Vivienda 2020",
            provider="INEGI",
            license="Libre uso",
            url="https://www.inegi.org.mx/programas/ccpv/2020/",
        )
        session.add(fuente)
        session.flush()
    return fuente


def _ensure_edicion(session, fuente, edition: str, publicada: date | None):
    from app.models import DataEdition

    ed = session.query(DataEdition).filter_by(
        source_id=fuente.source_id, edition=edition).one_or_none()
    if ed is None:
        ed = DataEdition(
            source_id=fuente.source_id, edition=edition,
            published_at=publicada,
        )
        session.add(ed)
        session.flush()
    return ed


def _leer_censo(zip_path: Path) -> list[dict]:
    with zipfile.ZipFile(zip_path) as z:
        entrada = [x for x in z.namelist()
                   if x.lower().endswith(".csv") and "conjunto_de_datos" in x][0]
        texto = io.TextIOWrapper(io.BytesIO(z.read(entrada)), encoding="utf-8-sig")
        return list(csv.DictReader(texto))


def _leer_geometrias(zip_path: Path, edo: str, log):
    import shapefile
    from pyproj import CRS, Transformer
    from shapely import wkt
    from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, shape
    from shapely.ops import transform as shp_transform

    with zipfile.ZipFile(zip_path) as z:
        with tempfile.TemporaryDirectory() as tmp:
            nombres = {}
            for entry in z.namelist():
                base = Path(entry).name
                if base.lower() in (f"{edo}a.shp", f"{edo}a.shx", f"{edo}a.dbf", f"{edo}a.prj"):
                    (Path(tmp) / base).write_bytes(z.read(entry))
                    nombres[base.lower()] = str(Path(tmp) / base)
            if f"{edo}a.shp" not in nombres:
                raise FileNotFoundError(f"Sin {edo}a.shp en {zip_path}")

            try:
                with open(nombres[f"{edo}a.prj"], "r", encoding="utf-8", errors="replace") as fh:
                    origen = CRS.from_wkt(fh.read())
            except Exception:
                origen = CRS.from_epsg(6362)
            transformador = Transformer.from_crs(origen, CRS.from_epsg(4326), always_xy=True)

            r = shapefile.Reader(nombres[f"{edo}a.shp"], encoding="latin-1")
            geoms: dict[str, str] = {}
            muestra = None
            for sr in r.iterShapeRecords():
                cvegeo = str(sr.record.as_dict().get("CVEGEO", "")).strip()
                geom = shape(sr.shape.__geo_interface__)
                if not geom.is_valid:
                    geom = geom.buffer(0)
                if isinstance(geom, GeometryCollection):
                    partes = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
                    geom = MultiPolygon(
                        [p for g in partes for p in (g.geoms if isinstance(g, MultiPolygon) else [g])]
                    )
                if isinstance(geom, Polygon):
                    geom = MultiPolygon([geom])
                if geom.is_empty:
                    continue
                geom = shp_transform(transformador.transform, geom)
                if muestra is None:
                    muestra = geom.centroid
                geoms[cvegeo] = wkt.dumps(geom, rounding_precision=6)
    if muestra is not None:
        log.info("CRS %s → EPSG:4326; centroide muestra: (%.4f, %.4f)",
                 origen.to_string(), muestra.x, muestra.y)
        if not (-118.5 <= muestra.x <= -86.0 and 14.0 <= muestra.y <= 33.5):
            raise ValueError("Geometrías fuera del rango de México; revisar CRS")
    return geoms


def main(argv: list[str] | None = None) -> int:
    parser = base_parser("Ingesta del Censo 2020 a nivel AGEB urbana con geometrías del MG")
    parser.add_argument("--edo", required=True, help="Clave de entidad (p. ej. 22)")
    parser.add_argument("--raw-dir", default=DEFAULT_RAW_DIR)
    parser.add_argument("--publicada", default="2021-07-26")
    args = parser.parse_args(argv)
    log = configurar_logging(args.log_level)
    edo = args.edo.zfill(2)
    log.info("censo_ageb: edición=%s entidad=%s dry_run=%s",
             args.edition, edo, args.dry_run)

    censo_zip = Path(args.raw_dir) / f"censo_{edo}.zip"
    mg_zip = Path(args.raw_dir) / f"mg_{edo}.zip"
    for p in (censo_zip, mg_zip):
        if not p.exists():
            raise FileNotFoundError(p)

    if args.dry_run:
        log.info("[dry-run] Leería %s y %s, cruzando AGEB urbana por CVEGEO",
                 censo_zip.name, mg_zip.name)
        return 0

    from geoalchemy2 import WKTElement
    from sqlalchemy import insert, text

    from app.db.session import SessionLocal
    from app.models import InegiAgeb

    publicada = None
    try:
        publicada = date.fromisoformat(args.publicada)
    except ValueError:
        pass

    filas = _leer_censo(censo_zip)
    agebs = [f for f in filas if f.get("MZA") == "000" and f.get("AGEB") not in (None, "", "0000")]
    log.info("%s: %d filas, %d AGEB urbanas (manzana 000, ageb != 0000)",
             censo_zip.name, len(filas), len(agebs))

    geoms = _leer_geometrias(mg_zip, edo, log)
    log.info("%s: %d geometrías AGEB urbana", mg_zip.name, len(geoms))

    session = SessionLocal()
    try:
        fuente = _ensure_fuente(session)
        ed = _ensure_edicion(session, fuente, args.edition, publicada)
        notes = (f"Entidad {edo}: Censo 2020 AGEB urbana (tercera edición) + "
                 f"Marco Geoestadístico 2020 ({edo}a.shp, LCC→WGS84). "
                 "NSE = proxy propio (Internet 35%, PC 25%, auto 25%, celular 15%); "
                 "grupo 25–29 estimado repartiendo POB15_64 − 15–17 − 18–24 − 60–64.")
        ed.notes = notes

        ya = session.execute(text(
            "SELECT 1 FROM prod.inegi_agebs WHERE edition_id = :eid AND cve_ent = :edo LIMIT 1"
        ), {"eid": ed.edition_id, "edo": edo}).first()
        if ya is not None and not args.force:
            log.warning("La edición %s ya tiene AGEB de %s; use --force", args.edition, edo)
            session.rollback()
            return 0

        session.execute(text(
            "DELETE FROM prod.inegi_agebs WHERE edition_id = :eid AND cve_ent = :edo"
        ), {"eid": ed.edition_id, "edo": edo})
        session.flush()

        lote: list[dict] = []
        insertados = 0
        sin_geom: list[str] = []
        bandas: dict[str, int] = {}
        for f in agebs:
            cve_ent = str(f["ENTIDAD"]).zfill(2)
            cve_mun = str(f["MUN"]).zfill(3)
            cve_loc = str(f["LOC"]).zfill(4)
            cve_ageb = str(f["AGEB"]).zfill(4)
            cvegeo = f"{cve_ent}{cve_mun}{cve_loc}{cve_ageb}"
            geom = geoms.get(cvegeo)
            if geom is None:
                sin_geom.append(cvegeo)
                continue

            pob_total = _int(f.get("POBTOT"))
            pob_0_14 = _int(f.get("POB0_14"))
            pob_15_64 = _int(f.get("POB15_64"))
            pob_65_mas = _int(f.get("POB65_MAS"))
            p15_17 = _int(f.get("P_15A17")) or 0
            p18_24 = _int(f.get("P_18A24")) or 0
            p60_mas = _int(f.get("P_60YMAS")) or 0
            p60_64 = max(0, p60_mas - (pob_65_mas or 0))
            r25_59 = max(0, (pob_15_64 or 0) - p15_17 - p18_24 - p60_64)
            en_25_29 = round(r25_59 * 5 / 35)
            pct_viv = {k: _pct(_int(f.get(mn)), _int(f.get("VIVPARH_CV")))
                       for k, mn in (("internet", "VPH_INTER"), ("computadora", "VPH_PC"),
                                     ("automovil", "VPH_AUTOM"), ("celular", "VPH_CEL"))}
            nse_score, nse_banda = _nse(pct_viv)
            if nse_banda:
                bandas[nse_banda] = bandas.get(nse_banda, 0) + 1

            prom = _dec(f.get("PROM_OCUP"))
            lote.append({
                "cvegeo": cvegeo,
                "cve_ent": cve_ent,
                "cve_mun": cve_mun,
                "cve_loc": cve_loc,
                "cve_ageb": cve_ageb,
                "ambito": AMBITO,
                "pob_total": pob_total,
                "pob_femenina": _int(f.get("POBFEM")),
                "pob_masculina": _int(f.get("POBMAS")),
                "pob_0_14": pob_0_14,
                "pob_15_29": p15_17 + p18_24 + en_25_29,
                "pob_30_59": r25_59 - en_25_29,
                "pob_60_mas": p60_mas,
                "pob_sin_clasificar": max(0, (pob_total or 0)
                                           - (pob_0_14 or 0) - (pob_15_64 or 0) - (pob_65_mas or 0)),
                "pea_ocupada": _int(f.get("POCUPADA")),
                "viv_habitadas": _int(f.get("VIVPAR_HAB")),
                "prom_ocupantes_viv": round(min(prom, 99.99), 2) if prom is not None else None,
                "pct_viv_internet": pct_viv["internet"],
                "pct_viv_computadora": pct_viv["computadora"],
                "pct_viv_automovil": pct_viv["automovil"],
                "pct_viv_celular": pct_viv["celular"],
                "nse_score": nse_score,
                "nse_banda": nse_banda,
                "geom": WKTElement(geom, srid=4326),
                "edition_id": ed.edition_id,
            })
            if len(lote) >= CHUNK:
                session.execute(insert(InegiAgeb), lote)
                insertados += len(lote)
                lote = []
        if lote:
            session.execute(insert(InegiAgeb), lote)
            insertados += len(lote)

        ed.records_total = (ed.records_total or 0) + len(agebs)
        ed.records_valid = (ed.records_valid or 0) + insertados
        ed.records_quarantine = (ed.records_quarantine or 0) + len(sin_geom)
        session.commit()
        log.info("AGEB %s: %d insertadas, %d sin geometría", edo, insertados, len(sin_geom))
        if sin_geom:
            log.warning("Sin geometría (primeras 10): %s", ", ".join(sin_geom[:10]))
        log.info("Distribución NSE: %s", dict(sorted(bandas.items())))
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
