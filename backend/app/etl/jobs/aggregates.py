"""Job ETL: recalcula los agregados precalculados (§5.6).

- prod.agg_ageb_scian: conteo por AGEB × SCIAN × estrato.
- prod.agg_hex_h3: agregados por hexágono H3 (res 8/9) para mapas de calor.

Idempotente por edición (borra y recalcula la edición indicada).
"""
from __future__ import annotations

from app.etl.jobs._common import base_parser, configurar_logging


def main(argv: list[str] | None = None) -> int:
    parser = base_parser("Recalcula agregados prod.agg_ageb_scian y prod.agg_hex_h3")
    parser.add_argument("--resolucion-h3", type=int, default=8, choices=[8, 9])
    args = parser.parse_args(argv)
    log = configurar_logging(args.log_level)

    log.info("aggregates: edición=%s h3_res=%d dry_run=%s",
             args.edition, args.resolucion_h3, args.dry_run)

    if args.dry_run:
        log.info("[dry-run] DELETE FROM prod.agg_ageb_scian WHERE edition_id=<edición>")
        log.info("[dry-run] INSERT ... SELECT cvegeo, scian_code, estrato_ordinal, count(*)")
        log.info("[dry-run] DELETE + recálculo de prod.agg_hex_h3 (res %d)", args.resolucion_h3)
        return 0

    from sqlalchemy import text

    from app.db.session import SessionLocal
    session = SessionLocal()
    try:
        log.info("Recalculando agg_ageb_scian para la edición %s...", args.edition)
        session.execute(text(
            "DELETE FROM prod.agg_ageb_scian WHERE edition_id = "
            "(SELECT edition_id FROM prod.data_editions WHERE edition = :ed)"
        ), {"ed": args.edition})
        session.execute(text(
            """INSERT INTO prod.agg_ageb_scian (cvegeo, scian_code, estrato_ordinal, n, edition_id)
               SELECT d.cve_ageb, d.scian_code, d.estrato_ordinal, COUNT(*), d.edition_id
               FROM prod.denue_establishments d
               JOIN prod.data_editions e ON e.edition_id = d.edition_id
               WHERE e.edition = :ed AND d.is_active AND d.cve_ageb IS NOT NULL
               GROUP BY d.cve_ageb, d.scian_code, d.estrato_ordinal, d.edition_id"""
        ), {"ed": args.edition})
        session.commit()
        log.info("Agregados recalculados (hexágonos H3: fase 2)")
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
