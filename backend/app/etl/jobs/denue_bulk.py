"""Job ETL: ingesta masiva del DENUE (paquete shapefile por entidad → prod).

Lee los paquetes ``denue_<ent>.zip`` del INEGI (atributos en DBF, puntos en
SHP), normaliza al DDL §5.3 y carga a las particiones de
``prod.denue_establishments``. Idempotente por (edición, entidad).

Uso:
    python -m app.etl.jobs.denue_bulk --edition DENUE_2026_05 --entidades 22 09
"""
from __future__ import annotations

import re
import tempfile
import unicodedata
import zipfile
from datetime import date, datetime
from pathlib import Path

from app.etl.jobs._common import base_parser, configurar_logging

SOURCE_CODE = "DENUE"
ENTIDADES = [f"{i:02d}" for i in range(1, 33)]
DEFAULT_RAW_DIR = "/code/data/raw"
CHUNK = 2000

LAT_MIN, LAT_MAX = 14.0, 33.5
LON_MIN, LON_MAX = -118.5, -86.0


def _norm(txt: object) -> str:
    t = unicodedata.normalize("NFKD", str(txt or ""))
    t = t.encode("ascii", "ignore").decode("ascii").lower().strip()
    return " ".join(t.split())


def _estrato_ordinal(txt: object) -> int:
    m = re.match(r"(\d+)", _norm(txt))
    if not m:
        return 1
    n = int(m.group(1))
    if n >= 251:
        return 7
    if n >= 101:
        return 6
    if n >= 51:
        return 5
    if n >= 31:
        return 4
    if n >= 11:
        return 3
    if n >= 6:
        return 2
    return 1


def _fecha(txt: object) -> date | None:
    if not txt:
        return None
    t = str(txt).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def _txt(val: object) -> str | None:
    if val is None:
        return None
    t = str(val).strip()
    return t or None


def _coord(val: object) -> float | None:
    try:
        return float(str(val).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _scian(val: object) -> str | None:
    t = str(val or "").strip()
    if not t:
        return None
    if t.isdigit() and len(t) <= 6:
        return t.zfill(6)
    return t[:6] or None


def _leer_zip_denue(zip_path: Path, log) -> list[dict]:
    import shapefile

    registros: list[dict] = []
    with zipfile.ZipFile(zip_path) as z:
        with tempfile.TemporaryDirectory() as tmp:
            for entry in z.namelist():
                if entry.lower().endswith((".shp", ".shx", ".dbf", ".prj")):
                    destino = Path(tmp) / Path(entry).name
                    destino.write_bytes(z.read(entry))
            shps = sorted(Path(tmp).glob("*.shp"))
            if not shps:
                raise FileNotFoundError(f"Sin .shp en {zip_path}")
            r = shapefile.Reader(str(shps[0]), encoding="latin-1")
            for rec in r.records():
                d = rec.as_dict()
                registros.append({k.lower(): v for k, v in d.items()})
    log.info("%s: %d registros leídos del DBF", zip_path.name, len(registros))
    return registros


def _ensure_fuente(session) -> object:
    from app.models import DataSource

    fuente = session.query(DataSource).filter_by(code=SOURCE_CODE).one_or_none()
    if fuente is None:
        fuente = DataSource(
            code=SOURCE_CODE,
            name="Directorio Estadístico Nacional de Unidades Económicas",
            provider="INEGI",
            license="Libre uso",
            url="https://www.inegi.org.mx/app/mapa/denue/",
        )
        session.add(fuente)
        session.flush()
    return fuente


def _ensure_edicion(session, fuente, edition: str, publicada: date | None, notas: str):
    from app.models import DataEdition

    ed = session.query(DataEdition).filter_by(
        source_id=fuente.source_id, edition=edition).one_or_none()
    if ed is None:
        ed = DataEdition(
            source_id=fuente.source_id, edition=edition,
            published_at=publicada, notes=notas,
        )
        session.add(ed)
        session.flush()
    elif notas:
        ed.notes = notas
    return ed


def main(argv: list[str] | None = None) -> int:
    parser = base_parser("Ingesta masiva del DENUE (shapefile por entidad)")
    parser.add_argument("--entidades", nargs="*", default=ENTIDADES,
                        help="Entidades a ingestar (default: las 32)")
    parser.add_argument("--raw-dir", default=DEFAULT_RAW_DIR,
                        help="Carpeta con los paquetes denue_<ent>.zip")
    parser.add_argument("--publicada", default="2026-05-20",
                        help="Fecha de publicación de la edición INEGI (AAAA-MM-DD)")
    args = parser.parse_args(argv)
    log = configurar_logging(args.log_level)
    log.info("denue_bulk: edición=%s entidades=%d dry_run=%s",
             args.edition, len(args.entidades), args.dry_run)

    publicada = _fecha(args.publicada)

    if args.dry_run:
        for ent in args.entidades:
            log.info("[dry-run] Leería %s/denue_%s.zip y cargaría a prod.denue_est_p%s",
                     args.raw_dir, ent, ent)
        return 0

    from geoalchemy2 import WKTElement
    from sqlalchemy import insert, text

    from app.db.session import SessionLocal
    from app.models.denue import DenueEstablishment

    session = SessionLocal()
    try:
        fuente = _ensure_fuente(session)
        notas = ("DENUE masivo por entidad (INEGI): " +
                 ", ".join(args.entidades))
        ed = _ensure_edicion(session, fuente, args.edition, publicada, notas)

        total_archivo = 0
        total_insertados = 0
        total_cuarentena = 0

        for ent in args.entidades:
            zip_path = Path(args.raw_dir) / f"denue_{ent}.zip"
            if not zip_path.exists():
                log.error("No existe %s; se omite la entidad %s", zip_path, ent)
                continue

            ya = session.execute(text(
                "SELECT 1 FROM prod.denue_establishments "
                "WHERE edition_id = :eid AND cve_ent = :ent LIMIT 1"
            ), {"eid": ed.edition_id, "ent": ent}).first()
            if ya is not None and not args.force:
                log.warning("La edición %s ya tiene datos de %s; use --force para reingestar",
                            args.edition, ent)
                continue

            session.execute(text(
                "DELETE FROM prod.denue_establishments "
                "WHERE edition_id = :eid AND cve_ent = :ent"
            ), {"eid": ed.edition_id, "ent": ent})
            session.flush()

            registros = _leer_zip_denue(zip_path, log)
            total_archivo += len(registros)

            vistos: set[str] = set()
            lote: list[dict] = []
            insertados = 0
            cuarentena = 0
            for reg in registros:
                denue_id = _txt(reg.get("id"))
                nombre = _txt(reg.get("nom_estab"))
                scian = _scian(reg.get("codigo_act"))
                lat = _coord(reg.get("latitud"))
                lon = _coord(reg.get("longitud"))
                cve_ent = _txt(reg.get("cve_ent")) or ent
                if (not denue_id or not nombre or not scian
                        or lat is None or lon is None
                        or not (LAT_MIN <= lat <= LAT_MAX)
                        or not (LON_MIN <= lon <= LON_MAX)
                        or not cve_ent.isdigit()):
                    cuarentena += 1
                    continue
                clave = f"{denue_id}|{cve_ent}"
                if clave in vistos:
                    cuarentena += 1
                    continue
                vistos.add(clave)

                per_ocu = _txt(reg.get("per_ocu")) or "0 a 5 personas"
                ageb = _txt(reg.get("ageb"))
                cve_loc = (_txt(reg.get("cve_loc")) or "0000").zfill(4)
                cve_ageb = (
                    f"{cve_ent}{(_txt(reg.get('cve_mun')) or '').zfill(3)}"
                    f"{cve_loc}{ageb.zfill(4)}"
                    if ageb else None
                )
                lote.append({
                    "denue_id": denue_id,
                    "clee": _txt(reg.get("clee")),
                    "nombre": nombre,
                    "razon_social": _txt(reg.get("raz_social")),
                    "scian_code": scian,
                    "scian_desc": _txt(reg.get("nombre_act")),
                    "estrato_texto": per_ocu,
                    "estrato_ordinal": _estrato_ordinal(per_ocu),
                    "tipo_vialidad": _txt(reg.get("tipo_vial")),
                    "nom_vialidad": _txt(reg.get("nom_vial")),
                    "num_exterior": _txt(reg.get("numero_ext")),
                    "num_interior": _txt(reg.get("numero_int")),
                    "colonia": _txt(reg.get("nomb_asent")),
                    "cp": (_txt(reg.get("cod_postal")) or "")[:5] or None,
                    "cve_ent": cve_ent,
                    "entidad": _txt(reg.get("entidad")),
                    "cve_mun": (_txt(reg.get("cve_mun")) or "").zfill(3)[:3] or None,
                    "municipio": _txt(reg.get("municipio")),
                    "localidad": _txt(reg.get("localidad")),
                    "cve_ageb": cve_ageb,
                    "cve_manzana": _txt(reg.get("manzana")),
                    "telefono": _txt(reg.get("telefono")),
                    "correo": _txt(reg.get("correoelec")),
                    "sitio_web": _txt(reg.get("www")),
                    "tipo_unidad": _txt(reg.get("tipounieco")),
                    "tipo_establecimiento": None,
                    "fecha_alta": _fecha(reg.get("fecha_alta")),
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "geom": WKTElement(f"POINT({round(lon, 6)} {round(lat, 6)})", srid=4326),
                    "edition_id": ed.edition_id,
                    "is_active": True,
                })
                if len(lote) >= CHUNK:
                    session.execute(insert(DenueEstablishment), lote)
                    insertados += len(lote)
                    lote = []
                    if insertados % 50000 == 0:
                        log.info("%s: %d insertados...", ent, insertados)
            if lote:
                session.execute(insert(DenueEstablishment), lote)
                insertados += len(lote)

            total_insertados += insertados
            total_cuarentena += cuarentena
            log.info("Entidad %s: %d válidos, %d en cuarentena", ent, insertados, cuarentena)

        ed.records_total = (ed.records_total or 0) + total_archivo
        ed.records_valid = (ed.records_valid or 0) + total_insertados
        ed.records_quarantine = (ed.records_quarantine or 0) + total_cuarentena
        session.commit()
        log.info("DENUE %s completado: %d válidos, %d en cuarentena de %d leídos",
                 args.edition, total_insertados, total_cuarentena, total_archivo)
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
