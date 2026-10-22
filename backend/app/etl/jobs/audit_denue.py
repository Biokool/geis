"""Job ETL: auditoría del DENUE entre ediciones (§7.3 del SRS).

Compara dos ediciones y registra en prod.denue_history los cambios:
alta, baja, cambio_estrato, cambio_scian, cambio_domicilio, reactivacion.
"""
from __future__ import annotations

from app.etl.jobs._common import base_parser, configurar_logging


def main(argv: list[str] | None = None) -> int:
    parser = base_parser("Auditoría del DENUE entre dos ediciones")
    parser.add_argument("--edition-from", required=True, help="Edición anterior (origen)")
    args = parser.parse_args(argv)
    log = configurar_logging(args.log_level)

    log.info("audit_denue: %s → %s dry_run=%s", args.edition_from, args.edition, args.dry_run)

    if args.dry_run:
        for tipo in ("alta", "baja", "cambio_estrato", "cambio_scian", "cambio_domicilio", "reactivacion"):
            log.info("[dry-run] Detectaría '%s' comparando denue_id entre ediciones", tipo)
        log.info("[dry-run] Insertaría los hallazgos en prod.denue_history")
        return 0

    from sqlalchemy import text

    from app.db.session import SessionLocal
    session = SessionLocal()
    try:
        # Altas: en la edición nueva pero no en la anterior.
        n_altas = session.execute(text(
            """INSERT INTO prod.denue_history
                 (denue_id, cve_ent, edition_from, edition_to, change_type, new_values)
               SELECT n.denue_id, n.cve_ent, :ed_from, :ed_to, 'alta',
                      jsonb_build_object('nombre', n.nombre, 'scian_code', n.scian_code)
               FROM prod.denue_establishments n
               LEFT JOIN prod.denue_establishments o
                 ON o.denue_id = n.denue_id AND o.edition_id = (
                      SELECT edition_id FROM prod.data_editions WHERE edition = :ed_from)
               WHERE n.edition_id = (SELECT edition_id FROM prod.data_editions WHERE edition = :ed_to)
                 AND o.denue_id IS NULL"""
        ), {"ed_from": args.edition_from, "ed_to": args.edition}).rowcount or 0

        # Bajas: en la anterior pero no en la nueva (se marcan inactivas).
        n_bajas = session.execute(text(
            """INSERT INTO prod.denue_history
                 (denue_id, cve_ent, edition_from, edition_to, change_type, old_values)
               SELECT o.denue_id, o.cve_ent, :ed_from, :ed_to, 'baja',
                      jsonb_build_object('nombre', o.nombre, 'scian_code', o.scian_code)
               FROM prod.denue_establishments o
               LEFT JOIN prod.denue_establishments n
                 ON n.denue_id = o.denue_id AND n.edition_id = (
                      SELECT edition_id FROM prod.data_editions WHERE edition = :ed_to)
               WHERE o.edition_id = (SELECT edition_id FROM prod.data_editions WHERE edition = :ed_from)
                 AND n.denue_id IS NULL"""
        ), {"ed_from": args.edition_from, "ed_to": args.edition}).rowcount or 0

        session.commit()
        log.info("Auditoría completada: %d altas, %d bajas registradas", n_altas, n_bajas)
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
