# GEIS — Changelog

> Registro cronológico del trabajo real sobre el repositorio. Reconstruido el 2026-10-21 desde la bitácora de las sesiones de integración (previo a la adopción de git). Formato: fecha + categorías.

## [2026-10-21] — Verificación E2E, fixes de integración, frontend autorizado, PKM + git

### Fixed
- **`/pipelines/runs` 500 → 200 OK**: 7 filas de `prod.runs.detalle` con arrays/NULL normalizadas a dict (ADR-005). Página Operación funcional.
- **`/leads?limit=1000/500` → 422**: `Mapa.tsx` (500→100), `Leads.tsx` y `Kpis.tsx` (1000→100) — contrato `le=100` respetado (ADR-004).
- **Mapa: controles encimados** — `ZoomControl` nativo movido a `topright`, `zoomControl={false}` en el contenedor; Geoman queda solo en topleft... (ambos grupos ahora flanquean el mapa sin solaparse).
- **Diagnóstico 404 `/api/runs/activos`**: pestaña del navegador con bundle obsoleto polleando cada 60 s — no es código actual; mitigación = hard refresh tras rebuild.

### Added
- **Dashboard KPI en `Inicio.tsx`** (excepción autorizada por el owner, ADR-004): KPIs generales por conteo real iterando cursor, etapas del pipeline, enriquecimiento Apollo, estado CRM y feed de corridas.
- `LeadCurado` (TS) extendido: `enriquecido_apollo?`, `crm_synced_at?` — espejo del modelo Pydantic.
- `.gitignore`: `backup_*.sql`, `signals/input.json`.
- **Documentación PKM completa**: `docs/` (overview, architecture, inventory, environment, dependencies, installation, deployment, testing, security, conventions, glossary, project-state, roadmap, backlog, changelog, ai-history, index), `docs/api/rest.md`, `docs/decisions/ADR-001..007`, `docs/sessions/`, `docs/working-memory/`.
- **Repositorio git inicial** (identidad GERAS / chino.mauries@gmail.com) — commit fundacional con todo el trabajo versionado.

### Changed
- `README.md`: PostGIS `16-3.5` (estaba 15-3.4) y descripción de la página Inicio (dashboard KPI).
- `geis-web` rebuilt 2 veces (bundles verificados servidos: `index-BosjGVjM.js`, `index-CsXbjQBn.js`).

### Verified
- radar-02 (run 20) OK: 158/160 leads con `temp_zona`, 40 `enriquecido_apollo`.
- `prod.leads`: 160 leads, 158 con geom para el mapa; `prod.denue_establishments`: 40 activos.
- `/api/v1/leads` y `/leads/curados` devuelven `lat/lon` desde host; `/leads/curados?limit=100` → 58 KB.
- `prod.user_investigations` = 0 filas → página Historial legítimamente vacía.

## [2026-10-20] — Cadena Radar completa E2E (01→05) + integraciones LinkedIn/HubSpot

### Added
- **Integración LinkedIn operativa** (ADR-006): OAuth manual (api detenida, canje de `code`, token a `.env`), `org_id` descubierto (`107784991`), provider configurado (token/org/vanity/expires), `05-linkedin-signals.json` corregido (endpoints Community Management + robustez), radar-05 OK en end-to-end (runs 4, 5) → `prod.linkedin_stats` + 1 señal cálida real.
- **Integración HubSpot operativa** (ADR-007): scope `crm.schemas.custom.write` (manual), 3 propiedades custom `biokool_etapa/score/linea` creadas vía API, provider `crm` cloud/hubspot habilitado, radar-04 sincroniza **160/160** leads (runs 18: 100, 19: 60).
- Apollo enrichment activado: provider `enrichment` → cloud/apollo (`PUT /api/v1/providers/enrichment`).
- Corrida de humo del gating: radar-04 sin precedentes → **409** correcto.

### Fixed
- **radar-02 "A 'json' property isn't an object"**: "Score y línea", "Extraer dominio" y "Merge Apollo" devuelven `{json:{...}}` (ADR-003). Runs 10, 11 y 20 OK.
- **radar-03 "Access to the file is not allowed"** (runs 12, 13): `N8N_RESTRICT_FILE_ACCESS_TO=/signals` en compose (primero mal formado, luego corregido a path único) + recreación de `geis-n8n`.
- **radar-03 "Unexpected token '~'" (run 14)**: BOM en JSON de Windows — nodo "Parsear JSON" (`extractFromFile`/`fromJson`) insertado y "Parsear señales" reescrito; run 15 OK, 3/3 señales procesadas (+2 leads → 160).
- **radar-04 "Preparar payload" (run 16)**: mismo contrato `{json:...}` (ADR-003); run 17 OK.
- `geis-web` reiniciado por caché DNS de Nginx tras cambios de red.
- Credencial `Postgres GEIS`: `ssl:false` (bool) rompía Postgres node v2.6 → re-import con `ssl:"disable"` (string); smoke test OK leyendo `prod.providers`.
- Task Broker de n8n CLI: conflicto de puerto resuelto con `N8N_RUNNERS_BROKER_PORT=5680`.
- Corridas atascadas marcadas `error` (runs 2, 3, 6, 8, 9, 16) — bitácora honesta.

### Verified
- **Cadena completa 01→05 en verde**: radar-01 (run 7) 146 leads crudos; radar-02 (runs 10, 11) 158→160 leads, enriquecimiento parcial→40 Apollo; radar-03 (run 15) señales; radar-04 (runs 18, 19) 160/160 HubSpot; radar-05 (runs 4, 5) LinkedIn.
- `stg.leads_raw` 146/146 `procesado=true`; `prod.warm_signals` procesadas.
- Workflow 03 en `runOnceForAllItems` (retornos de array válidos — sin cambios).

## [2026-10-19] — Infraestructura, PostGIS 16, aprovisionamiento n8n, scraper Playwright

### Added
- **Arranque completo**: `.env` desde `.env.example`, `docker compose up --build -d`, migraciones Alembic + seed, servicios base (`db`, `redis`, `api`, `web`) saludables, frontend en :3000, `geis-n8n` operativo con los 5 workflows en `n8n/workflows/`.
- **Scraper Playwright**: `requirements.txt` (+`playwright==1.49.0`) y `Dockerfile` (`python:3.11-slim-bookworm` + `playwright install --with-deps chromium`); imagen `geis-scraper:latest` 2.1 GB; smoke test `/scrape max_results=2` → 2 resultados.
- **`N8N_ENCRYPTION_KEY`** generada (64 hex) y persistida (`.env` + compose) — jamás rotar sin re-importar credenciales.
- **3 credenciales n8n** creadas programáticamente (`n8n import:credentials`): `Postgres GEIS`, `Apollo API`, `HubSpot` — IDs inyectados en las 22 referencias de los 5 workflows.
- **IDs Nanoid** inyectados en el campo `id` top-level de los 5 workflows → import = upsert idempotente (resolvió `EISDIR` importando por archivo y `null value in column "id"`).
- `N8N_URL`/`SCRAPER_URL` en `.env`; `docker-compose.yml`: encryption key en `n8n`, vars de nube (N8N, Apollo, LinkedIn, scraper) en `api`; validación `docker compose config` OK.
- Comentarios en `.env(.example)` mapeando variables ↔ nombres de credenciales en la UI de n8n.

### Changed
- **PostGIS 15-3.4 → 16-3.5** (ADR-001): backup `backup_pg15_20261019_2059.sql` (1.1 MB), volumen `geis_pgdata` recreado, migrate + seed re-aplicados.
- `.env`: eliminadas `N8N_BASIC_AUTH_USER/PASSWORD` (legado deprecado); duplicados consolidados.
- Limpieza de disco: imágenes huérfanas (~5 GB + ~6 GB) y build cache (~13.4 GB) — **~24 GB recuperados** en total.

### Fixed
- **Crash loop de `geis-n8n`** por mismatch de `N8N_ENCRYPTION_KEY` → resuelto al persistir la clave en compose.
- **"Unexpected token '﻿'" (BOM)** en JSON temporales de import — todo JSON para n8n/PowerShell se escribe **UTF-8 sin BOM** (convención global).

### Verified
- Apollo `healthy/logged_in`; Apify token OK (usuario `biokool`, plan FREE); estructura y contenido de `prod.providers`; 5 workflows intactos en DB n8n + owner existente; `.env`, `.env.example`, `docker-compose.yml` sin BOM; `geis-api` y `geis-n8n` recreados y saludables con el nuevo entorno.

## Referencias

- Detalle técnico de cada fix: [decisions/](decisions/) (ADR-001..007).
- Bitácora de sesiones con IA: [ai-history.md](ai-history.md), [sessions/](sessions/).
