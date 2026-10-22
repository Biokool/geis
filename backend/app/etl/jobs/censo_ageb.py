"""Job ETL: ingesta del Censo de Población y Vivienda a nivel AGEB.

Carga las variables de demanda (§2.2.2 / §5.2) a prod.inegi_agebs.
Idempotente por edición.
"""
from __future__ import annotations

from app.etl.jobs._common import base_parser, configurar_logging, edicion_ya_ingestada

SOURCE_CODE = "CPV2020"

VARIABLES = [
    "pob_total", "pob_femenina", "pob_masculina", "pob_0_14", "pob_15_29",
    "pob_30_59", "pob_60_mas", "pea_ocupada", "viv_habitadas",
    "prom_ocupantes_viv", "pct_viv_internet", "pct_viv_computadora",
    "pct_viv_automovil", "pct_viv_celular",
]


def main(argv: list[str] | None = None) -> int:
    parser = base_parser("Ingesta del Censo (AGEB) a prod.inegi_agebs")
    args = parser.parse_args(argv)
    log = configurar_logging(args.log_level)

    log.info("censo_ageb: edición=%s variables=%d dry_run=%s",
             args.edition, len(VARIABLES), args.dry_run)

    if args.dry_run:
        log.info("[dry-run] Leerías los tabulados del Censo por AGEB del INEGI")
        log.info("[dry-run] Mapearías %d variables a prod.inegi_agebs", len(VARIABLES))
        log.info("[dry-run] Calcularías nse_score/nse_banda (proxy AMAI §3.9)")
        log.info("[dry-run] Registrarías la edición %s en prod.data_editions", args.edition)
        return 0

    from app.db.session import SessionLocal
    session = SessionLocal()
    try:
        if edicion_ya_ingestada(session, SOURCE_CODE, args.edition) and not args.force:
            log.warning("La edición %s ya está ingerida; use --force para reingestar", args.edition)
            return 0
        # TODO(fase 2): lectura real de tabulados + cálculo de NSE.
        log.info("Job completado (stub funcional)")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
