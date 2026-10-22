# ADR-001: Upgrade de PostGIS 15-3.4 → 16-3.5 con recreación del volumen

- **Fecha:** 2026-10-19
- **Estado:** Accepted
- **Autor:** Claude Code (sesión opencode, GLM)
- **Origen:** Claude Code

## Contexto

GEIS corría `postgis/postgis:15-3.4`. Se quería la línea PostGIS 3.5 sobre PostgreSQL 16 (mejoras de GEOS/ProJ, funciones y rendimiento para los modelos espaciales de GEIS).

## Problema

Postgres no permite saltos menores in-place dentro del volumen: cambiar el tag de la imagen sin recrear `pgdata` corrompe/impide el arranque. El volumen contenía ya datos sembrados y de operación.

## Alternativas consideradas

1. **No actualizar** — cero riesgo, pero congela la línea 15/EOL más pronto.
2. **pg_upgrade dentro del contenedor** — complejo en Docker Compose con imagen única, sin beneficio claro en local.
3. **Backup → recrear volumen → restore → migrate+seed** — simple, reproducible, costo: ventana manual.

## Decisión

Backup completo con `pg_dump` (guardado como `backup_pg15_20261019_2059.sql`, 1.1 MB), recreación del volumen `geis_pgdata`, imagen `postgis/postgis:16-3.5`, re-aplicación de `make migrate` + `make seed` y re-import de datos de operación.

## Justificación

Es la vía documentada por la imagen oficial para upgrades mayores; en un dataset de desarrollo (decenas de cientos de leads) el costo de restore es minutos. El backup queda como artefacto de rollback en la raíz (excluido de git).

## Consecuencias

- Postgres 16 + PostGIS 3.5 operativos; README actualizado.
- `db/init.sql` vuelve a ejecutarse al crear el volumen (extensiones + esquemas) — recordar `make migrate` tras cualquier recreación.
- Rollback: restaurar `backup_pg15_20261019_2059.sql` contra la imagen 15-3.4 con volumen nuevo.

## Impacto

- Contenido: `docker-compose.yml` (tag), volumen `geis_pgdata`, README.
- Usuarios: ninguno en runtime (ventana de mantenimiento única).

## Referencias

- [deployment.md](../deployment.md) (sección migraciones) · [changelog.md](../changelog.md)
