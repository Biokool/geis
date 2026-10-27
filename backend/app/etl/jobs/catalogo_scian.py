"""Job ETL: carga/actualiza el catálogo SCIAN curado y los alias de giro.

Toma las ``--top`` clases SCIAN más frecuentes del DENUE cargado, les aplica
los parámetros por sector y las excepciones de ``app.data.catalogo_scian`` y
registra los alias de giro. No depende de una edición: es un catálogo vivo.

Uso:
    python -m app.etl.jobs.catalogo_scian --top 200
"""
from __future__ import annotations

import argparse

from sqlalchemy import text

from app.data.catalogo_scian import (
    ALIASES,
    DEFAULT_PARAMS,
    OVERRIDES,
    SECTOR_PARAMS,
)
from app.etl.jobs._common import configurar_logging


def _params(codigo: str) -> tuple[float, float, float]:
    if codigo in OVERRIDES:
        return OVERRIDES[codigo]
    return SECTOR_PARAMS.get(codigo[:2], DEFAULT_PARAMS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Carga el catálogo SCIAN curado y los alias de giro")
    parser.add_argument("--top", type=int, default=200,
                        help="Clases más frecuentes del DENUE a incluir (default: 200)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)
    log = configurar_logging(args.log_level)
    log.info("catalogo_scian: top=%d dry_run=%s", args.top, args.dry_run)

    if args.dry_run:
        log.info("[dry-run] %d clases top + %d códigos con alias; %d alias",
                 args.top, len(ALIASES),
                 sum(len(v) for v in ALIASES.values()))
        return 0

    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        desc_map = dict(session.execute(text(
            """SELECT DISTINCT ON (scian_code) scian_code, scian_desc
               FROM (
                   SELECT scian_code, scian_desc, COUNT(*) AS n
                   FROM prod.denue_establishments
                   WHERE scian_desc IS NOT NULL AND scian_desc <> ''
                   GROUP BY scian_code, scian_desc
               ) s
               ORDER BY scian_code, n DESC"""
        )).all())

        top = session.execute(text(
            """SELECT scian_code, COUNT(*) AS n
               FROM prod.denue_establishments
               GROUP BY scian_code
               ORDER BY n DESC
               LIMIT :top"""
        ), {"top": args.top}).all()

        codigos = [f[0] for f in top if f[0] in desc_map]
        extra = [c for c in ALIASES if c in desc_map and c not in codigos]
        codigos += extra
        alias_descartados: list[str] = []

        filas = [
            {
                "scian_code": codigo,
                "description": desc_map[codigo],
                "sector_code": codigo[:2],
                "thermal": _params(codigo)[0],
                "attr": _params(codigo)[1],
                "lam": _params(codigo)[2],
            }
            for codigo in codigos
        ]
        if filas:
            session.execute(text(
                """INSERT INTO prod.cat_scian
                     (scian_code, description, scian_version, sector_code,
                      thermal_intensity, base_attractiveness, lambda_default, updated_at)
                   VALUES (:scian_code, :description, '2023', :sector_code,
                           :thermal, :attr, :lam, now())
                   ON CONFLICT (scian_code) DO UPDATE SET
                     description = EXCLUDED.description,
                     sector_code = EXCLUDED.sector_code,
                     thermal_intensity = EXCLUDED.thermal_intensity,
                     base_attractiveness = EXCLUDED.base_attractiveness,
                     lambda_default = EXCLUDED.lambda_default,
                     updated_at = now()"""
            ), filas)
        log.info("cat_scian: %d clases upserted (top %d del DENUE + %d con alias)",
                 len(filas), args.top, len(extra))

        alias_filas = []
        for codigo, etiquetas in ALIASES.items():
            if codigo not in desc_map:
                alias_descartados.append(codigo)
                continue
            for etiqueta, confianza in etiquetas:
                alias_filas.append({
                    "giro_label": etiqueta,
                    "scian_code": codigo,
                    "confidence": confianza,
                })
        if alias_filas:
            session.execute(text(
                """INSERT INTO prod.cat_giro_scian (giro_label, scian_code, confidence)
                   VALUES (:giro_label, :scian_code, :confidence)
                   ON CONFLICT (giro_label, scian_code) DO UPDATE SET
                     confidence = EXCLUDED.confidence"""
            ), alias_filas)
        session.commit()
        log.info("cat_giro_scian: %d alias para %d clases", len(alias_filas),
                 len(ALIASES) - len(alias_descartados))
        if alias_descartados:
            log.warning("Clases con alias sin datos en el DENUE cargado: %s",
                        ", ".join(sorted(set(alias_descartados))))
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
