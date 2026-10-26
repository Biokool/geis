# GEIS — Changelog

> Registro cronológico del trabajo real sobre el repositorio. Reconstruido el 2026-10-21 desde la bitácora de las sesiones de integración (previo a la adopción de git). Formato: fecha + categorías.

## [2026-10-26] — Validación funcional E2E completa: cadena real, rama warm del 03 y filtros geo operativos

> Recorrido función por función contra el stack real, corrigiendo los bugs
> encontrados por el camino. Detalle y aprendizajes en `sessions/2026-10-26.md`.

### Fixed
- **`geis-api` sin mounts de `docs/` y `n8n/`** → 2 failed + 3 errors de tests por `FileNotFoundError`; añadidos `./docs:/docs:ro` y `./n8n:/n8n:ro`.
- **Webhooks n8n muertos:** `webhookId` UUID faltante en los 5 nodos Webhook → `POST /webhook/radar-0X` ahora 200 `{"message":"Workflow was started"}`.
- **Cron 02 inválido** (`0 30 6 * * 1` → `WorkflowActivationError`) → `30 6 * * 1`.
- **Run atascado radar-03:** un nodo Postgres con 0 items se salta y la cadena moría sin callback. `Armar warm` emite marcador `skip` cuando no hay señales y los SQL de upsert llevan guardas `AND {{ $json.skip ? 'false' : 'true' }}`. Run 27 marcado `error` con motivo (bitácora append-only).
- **SCIAN rechazado en Analizar:** `resolver_scian` (analysis/derive) acepta SCIAN con descripción de giro.
- **500 en Analizar con giro de texto libre** ([ADR-010]): `context.py` consultaba `prod.knowledge_facts`, tabla que vive en `public` (migración 0003, compatibilidad SQLite); el `except` tragaba el error sin rollback → `InFailedSqlTransaction` → el 500 estallaba después en el commit del reporte. Fix: SQL sin esquema + `safe_rollback(db)` en los 7 `except` SQL de la ruta (context, `_common`, `analysis`, reports, leads).

### Added
- **[ADR-009] Fallback geo desde la dirección formateada** (`leads.py::_parsear_direccion_geo`): AGEB → DENUE → texto, solo rellena NULL. Formato Google MX («Calle, Colonia, 76000 Municipio, Qro.»); abreviaturas de las 32 entidades normalizadas; `México` a secas = país, nunca entidad; la calle jamás se toma como colonia. Excepción acotada a AGENTS.md.
- **[ADR-010] `safe_rollback(db)`** (`app/db/session.py`): todo `except` que traga un error SQL limpia la sesión (best-effort, tolerante a fakes de tests) — fin del patrón causa-1.ª/estallido-2.º. +2 tests de regresión.

### Verified
- **`pytest` 139/139** (+2 del parser geo, +2 de regresión ADR-010).
- **E2E del fix ADR-010:** giro que causaba el 500 → **201** `verdict:"AVANZAR"` (14 secciones); auto-aprendizaje en `public.knowledge_facts` (`report_insight:58f308bd`); 2.º POST → 201; `GET /reports/{id}` → 200.
- **Sweep de API:** 15 GETs 200; CRUD reports/investigations/proposals/share/export; 422 legítimos documentados (`{}` en reports/signals, compare sin `scian`/`giro`).
- **Cadena 01→05 en verde con scrape real de Querétaro:** radar-01 (run 24, target Centro 76000, giros bodegas, ~3 min Playwright) → 18 leads nuevos; 25 (02), 29 (03 vacío), 28 (04), 26 (05).
- **Señal warm real:** `POST /signals` → radar-03 run 30 ok; señal `procesada=true`; lead manual +25 creado.
- **Filtros geo con datos reales:** `enrich-geo` `actualizados=158`; `entidad=Querétaro` → 82 leads; `+municipio` → 75; `+colonia=Centro` → 17; `cp=76000` → 18; cascada `geo-filters` poblada.
- **`b2b-prospecting` y `lookalike`** con datos reales (Condesa CDMX): 200 con scores y ranking de similitud AGEB.

### Notes
- `pendientes=176` tras el enrich es casi todo `scian`: solo DENUE cercano (≤500 m, 40 establecimientos) puede darlo — crecer DENUE o mapear giro→SCIAN queda en backlog.
- `n8n update:workflow` deprecado en 2.35: usar `publish:workflow --id=<id>` y reiniciar n8n tras importar.
- Working tree completo commiteado y empujado a `origin` (2 secciones, ADR-008/009/010, fixes de cadena, docs PKM).
- Colonias atípicas del texto de Google (p. ej. «Lib. Norponiente Km 18-Bodega A5») aparecen tal cual en el catálogo — calidad limitada por la fuente.

## [2026-10-25] — Integración local de las 2 secciones: migraciones, E2E real y rebuild

> Cierre en la máquina del owner de lo que `REVISION-2-SECCIONES.md` dejó como
> pendiente por no tener Docker: todo lo de abajo se ejecutó contra el PostGIS
> real, n8n y los servicios externos (no fakes).

### Verified
- **`pytest` 135/135** dentro del contenedor `geis-api` (incluye `test_seccion1.py` 22 y `test_seccion2.py` 16).
- **Migraciones 0004 → 0005 → 0006 aplicadas** (`alembic upgrade head`): 5 columnas geo + 6 índices en `prod.leads`, tabla `prod.report_shares` y `prod.user_investigations.es_principal`.
- **`POST /leads/enrich-geo` real** (160 leads): `actualizados=144`, `con_geometria=158`, `sin_datos=2`; CP derivado en 144 leads. Entidad/municipio solo en 1 porque el seed trae **4 AGEB** (cobertura real pendiente del ETL censal completo).
- **Geocoding real**: link de Maps (`@lat,lon`) → `fuente=link_maps`; dirección en texto → Nominatim → `fuente=nominatim` con CP 06700. Sin punto por defecto.
- **Reporte real** (Roma Norte, SCIAN 722515): 201, veredicto **AVANZAR**, 24 claves de payload; 15 atractores, 15 competidores, 9 categorías de entorno, 3 isócronas **reales de Valhalla** (5/10/15 min) con población y competidores, NSE alto, delivery y break-even.
- **Compartir**: `POST /reports/{id}/share` → 201, lectura pública → 200, revocación → 204, lectura posterior → **404**.
- **Comparador** (`POST /analysis/compare`, 2 puntos directos) y **CRUD de investigaciones** (`POST` → `PATCH es_principal` → `DELETE` 204 → `GET` 404) contra la BD real.
- **Frontend rebuild** (`docker compose build web` + `up -d web`): bundle `index-BdB0KMtG.js`; `/analizar`, `/panel-radar`, `/reporte/{id}/imprimir` y `/r/{token}` responden 200 por el fallback SPA.

### Notes
- Overpass respondió **502 (servidor a capacidad)** durante la prueba: el conector devuelve `[]` y el reporte sale sin vialidades (no inventa vías); el proxy vehicular cae a su basal poblacional.
- El endpoint `POST /leads/enrich-geo` es idempotente (`COALESCE`): reejecutar no pisa campos ya llenados.
- Docs actualizadas en esta sesión: README, `GUIA-DE-INICIO`, `ARQUITECTURA-2-SECCIONES`, `api/rest`, `architecture`, `inventory`, `environment`, `project-state`, `backlog`, `working-memory`, `sessions/2026-10-25.md`, ADR-008.

## [2026-10-21 (noche)] — Reestructuración en 2 secciones: Ubicaciones + Radar

> Encargo: partir el producto en dos secciones reales (Sabueso IA / Biokool
> Radar) con «más funciones y menos clicks». Diseño y trazabilidad en
> `ARQUITECTURA-2-SECCIONES.md` (normativo), `INVENTARIO-SABUESO.md` (53
> funciones), `INVENTARIO-RADAR.md` (102 + R1–R17) y `REVISION-2-SECCIONES.md`
> (validación). Baseline: 97 tests.

### Added
- **Sección 1 · Ubicaciones — backend:** geocoding real (`app/geo/geocoding.py`: parser de links de Maps, links cortos, Nominatim search/reverse; 422 en vez de punto falso), contexto completo del reporte (`app/reports/context.py`: población/segmentos/hogares/PEA/NSE, entorno de 9 categorías, competencia con anillos y «PARECE ACTIVO», atractores, isócronas y vialidades), conectores `overpass.py` (vialidades) y `valhalla.py` (isócronas con fallback honesto a radios), analítica `anclas.py` (efecto ancla en Huff), `categorias.py` (9 rangos SCIAN), `movilidad.py` (proxies §3.10 siempre `estimado`) y `sector_data.py` (fichas de 15 giros, TAM editable, break-even).
- **Sección 1 — API:** `POST /analysis/compare` (2–6 items: investigaciones o puntos directos), `DELETE`/`PATCH /investigations/{id}`, `POST /reports/{id}/share` + `GET /reports/shared/{token}` + `DELETE /reports/{id}/share/{token}`, overrides TAM en `POST /reports`, geocode enriquecido (componentes + fuente).
- **Sección 1 — frontend:** `Analizar` (giro + dirección/link → pin arrastrable → reporte en un clic), `Aprende`, `ReportePrint` (`/reporte/{id}/imprimir`, CSS print), `ReporteCompartido` (`/r/{token}`), Reporte con mapas Leaflet (anillos, atractores, isócronas), dona ECharts, acordeones, calculadoras de renta y punto de equilibrio, botones WhatsApp/PDF/link invitado.
- **Sección 2 · Radar:** `PanelRadar` (4 alertas, 4 KPIs, 4 gráficas), Operación con las 5 etapas y gating, providers, LinkedIn y clima; filtros **entidad/municipio/colonia/CP/SCIAN** con cascada (`GET /catalogs/geo-filters`), `POST /leads/enrich-geo`, `GET /leads/count` y `?modo=radar` en el Mapa; migración **0005** (columnas geo) y **0006** (`report_shares`, `es_principal`).
- **Navegación:** selector fijo **📍 Ubicaciones | 🎯 Radar** en el sidebar con persistencia (`localStorage: geis:seccion`); Inicio y grupo Sistema comunes.
- **Tests:** `backend/tests/test_seccion1.py` (22) y `test_seccion2.py` (16) — total **135**.
- **Docs normativas:** `INVENTARIO-SABUESO.md`, `INVENTARIO-RADAR.md`, `ARQUITECTURA-2-SECCIONES.md`, `REVISION-2-SECCIONES.md`.

### Changed
- `n8n/workflows/02-dedup-score.json`: nodo HTTP opcional de `enrich-geo` tras el scoring.
- README y `GUIA-DE-INICIO.md`: el relato del producto pasa de 5 grupos a 2 secciones.

## [2026-10-21 (tarde)] — Revisión profunda: producto unificado

> Encargo del owner (diagnóstico completo en `REVISION-PROFUNDA.md`): la fusión GEIS×Radar no contaba una historia ni mostraba un proceso; corrección orientada a **producto** ejecutada por asistente externo y verificada al integrar.

### Added
- **Backend — 3 endpoints nuevos:** `GET /leads/count` (total real de `prod.leads` con filtros etapa/línea/source; reemplaza el conteo por cursor 5×100), `POST /analysis/compare` (2–5 investigaciones: veredicto, ISM, TAM, competencia, población, Huff reutilizando `compute_location_analysis`), `DELETE /investigations/{id}` (204, físico con cascade). Esquemas `LeadCountOut`, `CompareRequest/Item/Response`.
- **Navegación en 5 grupos** (Inicio · 1 Inteligencia · 2 Prospección · 3 Operación · 4 Sistema) con **badge de total de leads** en el menú.
- **Inicio = centro de mando:** checklist «Primeros pasos» con estado real (perfil → datos → investigación → leads → corrida) + KPIs + actividad reciente.
- **Leads unificados:** adaptador `LeadUnificado` (`desdeEspacial`/`desdeRadar`) — UNA tabla con columna/filtro de origen (Espacial/Radar), contador real y ficha drawer.
- **Mapa:** panel de capas conmutables con conteos, leyenda visible y acciones desde el popup.
- **Comparador real** (tabla de métricas con celda verde por fila y «elegir ganadora») e **Historial** con reabrir en Mapa / ver Reporte / comparar / borrar.
- `backend/tests/test_correccion_profunda.py` (3 endpoints nuevos con fakes; sin red ni Postgres).
- Docs: `GUIA-DE-INICIO.md` (proceso de 5 momentos), `REVISION-PROFUNDA.md` (diagnóstico + diseño rector), enlace en README.

### Changed
- `Reporte.tsx` polish y estados vacíos guiados con enlaces cruzados en Operación/Geofencing/Exportación/KPIs; README actualizado (Fase 2 sin `DELETE`, portada = centro de mando).

### Verified
- Contrato frontend↔backend alineado: `/leads/count`, `/analysis/compare`, `DELETE /investigations/{id}` (`api.ts` ↔ routers ↔ `test_correccion_profunda.py`).
- Escaneo de secretos del nuevo contenido: limpio (ningún valor real del `.env` presente).

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
