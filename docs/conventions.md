# GEIS — Convenciones

## Regla maestra de contribución (AGENTS.md)

- **`backend/app` y `frontend/src` son territorio de workers**: no tocar sin autorización explícita del owner. En las sesiones de octubre 2026 el owner autorizó expresamente: fix de leyenda del mapa, fixes de `limit`, extensión de `LeadCurado` en `api.ts` y el dashboard de `Inicio.tsx`.
- Toda excepción queda documentada en el changelog con su origen.

## Git

- Repositorio en la raíz `geis/`. Commits en español, imperativo, con contexto del *porqué*.
- **Nunca** commitear: `.env`, `backup_*.sql`, `signals/input.json`, `node_modules/`, `dist/`, `pgdata/`, `__pycache__/`, `.pytest_cache/`.
- Verificar staging con `git status` antes de cada commit.

## Codificación

- **UTF-8 sin BOM, siempre**. El BOM rompe `JSON.parse` en n8n (`Unexpected token '~'` / `'﻿'`). Al generar JSON desde PowerShell, validar que no empieza con `EF BB BF`.

## n8n (ver ADR-003)

- Code nodes (JS) en modo `runOnceForEachItem` devuelven `{ json: {...} }`; nunca arrays crudos.
- En modo `runOnceForAllItems` el retorno de array de items sí es válido.
- Archivos leídos por workflows: solo `/signals` (restricción del contenedor).
- Workflows versionados en `n8n/workflows/*.json` con **ID (Nanoid) estable en el top-level** → import = upsert idempotente.
- Credenciales referenciadas por **ID** inyectado, no por nombre.
- Ejecución CLI contra el contenedor: `-e N8N_RUNNERS_BROKER_PORT=5680`.

## Backend

- Modelos Pydantic estrictos: si una columna puede ser dict, nunca permitir array ni NULL (`prod.runs.detalle` — ADR-005).
- Paginación por cursor: `limit ≤ 100` en `/leads*` (los clientes DEBEN iterar `next_cursor`); `/pipelines/runs` acepta hasta 200.
- Migraciones solo por Alembic; jamás `CREATE TABLE` manual en `prod` (los fixes puntuales de datos van como UPDATE y se documentan).

## Frontend

- Cliente HTTP central en `src/lib/api.ts` con interfaces TS espejo de los modelos Pydantic (nueva columna ⇒ nueva propiedad opcional en la interfaz).
- Datos masivos: siempre paginar (no asumir `total`); los endpoints no lo devuelven.
- Estilo: Tailwind + componentes shadcn existentes; gráficos con ECharts (`echarts-for-react`), mapas con react-leaflet.
- Tras cambiar frontend: rebuild de `geis-web` + hard refresh del navegador (las pestañas viejas pollean bundles obsoletos).

## Documentación (PKM)

- `docs/` es la fuente de verdad; working-memory se refresca, el archivo histórico (sessions/decisions/changelog) **solo crece**.
- Cada decisión significativa ⇒ ADR nuevo (`docs/decisions/ADR-NNN-slug.md`, numeración monotónica).
- Discrepancia docs↔código: manda el código; se corrige la doc y se registra en la sesión del día.
