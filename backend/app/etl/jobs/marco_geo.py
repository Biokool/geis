"""Job ETL: ingesta del Marco Geoestadístico (entidades, municipios, AGEB, manzanas).

Carga las geometrías oficiales a prod.marco_* y prod.inegi_agebs/manzanas.
Idempotente por edición.
"""
from __future__ import annotations

from app.etl.jobs._common import base_parser, configurar_logging, edicion_ya_ingestada

SOURCE_CODE = "MARCO2024"

CAPAS = ["marco_entidades", "marco_municipios", "inegi_agebs", "inegi_manzanas"]


def main(argv: list[str] | None = None) -> int:
    parser = base_parser("Ingesta del Marco Geoestadístico a prod.marco_*")
    args = parser.parse_args(argv)
    log = configurar_logging(args.log_level)

    log.info("marco_geo: edición=%s capas=%s dry_run=%s", args.edition, CAPAS, args.dry_run)

    if args.dry_run:
        log.info("[dry-run] Descargarías los shapefiles/GeoJSON del Marco Geoestadístico")
        for capa in CAPAS:
            log.info("[dry-run] Cargarías prod.%s (SRID 4326, índice GiST)", capa)
        log.info("[dry-run] Registrarías la edición %s en prod.data_editions", args.edition)
        return 0

    from app.db.session import SessionLocal
    session = SessionLocal()
    try:
        if edicion_ya_ingestada(session, SOURCE_CODE, args.edition) and not args.force:
            log.warning("La edición %s ya está ingerida; use --force para reingestar", args.edition)
            return 0
        # TODO(fase 2): descarga y carga real con validación topológica.
        log.info("Job completado (stub funcional)")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
