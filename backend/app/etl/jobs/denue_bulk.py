"""Job ETL: ingesta masiva del DENUE (descarga por entidad → staging → prod).

Idempotente por edición: si la edición ya existe en prod.data_editions y no
se pasa --force, el job termina sin escribir.
"""
from __future__ import annotations

from app.etl.jobs._common import base_parser, configurar_logging, edicion_ya_ingestada

SOURCE_CODE = "DENUE"
ENTIDADES = [f"{i:02d}" for i in range(1, 33)]


def main(argv: list[str] | None = None) -> int:
    parser = base_parser("Ingesta masiva del DENUE por entidad (01–32)")
    parser.add_argument("--entidades", nargs="*", default=ENTIDADES,
                        help="Entidades a ingestar (default: las 32)")
    args = parser.parse_args(argv)
    log = configurar_logging(args.log_level)

    log.info("denue_bulk: edición=%s entidades=%d dry_run=%s",
             args.edition, len(args.entidades), args.dry_run)

    if args.dry_run:
        log.info("[dry-run] Descargaría %d archivos del INEGI (uno por entidad)", len(args.entidades))
        log.info("[dry-run] Normalizaría columnas al DDL §5.3, validaría geometrías y estratos")
        log.info("[dry-run] Cargaría a stg.denue_raw y luego a prod.denue_establishments (particiones p01–p32)")
        log.info("[dry-run] Registraría la edición %s en prod.data_editions", args.edition)
        return 0

    from app.db.session import SessionLocal
    session = SessionLocal()
    try:
        if edicion_ya_ingestada(session, SOURCE_CODE, args.edition) and not args.force:
            log.warning("La edición %s ya está ingerida; use --force para reingestar", args.edition)
            return 0
        # TODO(fase 2): descarga real del INEGI + carga a staging + validación.
        log.info("Descargando %d entidades... (stub: conectar conector INEGI)", len(args.entidades))
        log.info("Job completado (stub funcional)")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
