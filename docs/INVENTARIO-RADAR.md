# INVENTARIO EXHAUSTIVO — Repositorio Biokool Radar

> **Propósito:** lista de verificación oficial de TODAS las funciones que la
> nueva Sección 2 del sistema debe contener («todas absolutamente todas»).
> **Método:** lectura completa del repo `~/workspace/biokool-radar/` —
> `README.md`, `CHANGES.md`, `docs/ARQUITECTURA.md`, `docs/guia-usuario.html`,
> `docs/documentacion-tecnica.html`, `dashboard/server.js` (408 líneas),
> `dashboard/public/index.html` + `app.js` (734 líneas), `scraper/app.py`
> (239 líneas) + `scraper/README.md`, `db/init.sql` + `db/migrate.sql`,
> los 5 `n8n/workflows/*.json` (nodo por nodo, con su código JS y SQL),
> `signals/input.json`, `.env.example` y `docker-compose.yml`.
> **Regla de verdad:** cuando un .md y el código discrepan, manda el código
> (se anota la discrepancia). Versión del sistema: Radar v3 (CHANGES.md,
> 2026-10-10); `/api/config` reporta `version: 'v1.1'`.

---

## 1. Tabla maestra de funciones

### A. Infraestructura y arranque

| # | Función | Dónde vive | Entradas → Salidas |
|---|---|---|---|
| 1 | Stack de 5 servicios Docker: `postgres` (postgres:16, BDs `radar` + `n8n`), `n8n`, `dashboard` (:3000), `scraper` (:5000), `cloudflared` | `docker-compose.yml` | `docker compose up -d --build` → ecosistema completo local, costo $0 |
| 2 | Esquema inicial de BD (corre solo con volumen `pgdata` nuevo): crea BD `n8n` y 7 tablas (`leads_raw`, `leads`, `proposals`, `runs`, `providers`, `linkedin_stats`, `warm_signals`) + seed de 6 providers | `db/init.sql` | Volumen vacío → esquema completo |
| 3 | Migración idempotente para volúmenes viejos (re-ejecutable, no borra datos) | `db/migrate.sql` | BD vieja → tablas/columnas nuevas + limpia leads `EJEMPLO - %` |
| 4 | **Auto-migración al arrancar el dashboard** (`initDb()`): crea `providers` + seed, columnas `enriquecido_apollo`, `crm_synced_at`, `notas`, tablas `linkedin_stats` y `warm_signals`; borra filas `EJEMPLO - %` de `leads` y `leads_raw` | `dashboard/server.js` `initDb()` | Arranque del dashboard → BD siempre al día aunque el volumen sea viejo |
| 5 | Túnel público Cloudflare (quick tunnel) al dashboard | `docker-compose.yml` servicio `cloudflared` | `docker compose logs cloudflared` → URL `https://*.trycloudflare.com` pública |
| 6 | Variante protegida del túnel: acceso solo con PIN por email autorizado (`--allowed-mail`, dominios con `*@dominio`) | `README.md` → «Variante protegida» | `cloudflared tunnel --url http://localhost:3000 --allowed-mail tu@email.com` → acceso restringido por email |
| 7 | Backup de la BD completa (leads, runs, providers, tokens) | `README.md` / `docs/documentacion-tecnica.html` §10 | `pg_dump -U postgres radar` → archivo `backup-radar-AAAA-MM-DD.sql`; restore documentado (bajar stack, recrear volumen, `psql`) + respaldo aparte del volumen `n8n_data` (tar) |
| 8 | Configuración por variables de entorno (todas las keys viven SOLO en `.env`, nunca en UI ni en git) | `.env.example` | `POSTGRES_DB/USER/PASSWORD`, `N8N_ENCRYPTION_KEY` (64 hex), `N8N_API_KEY`, `N8N_WEBHOOK_01…05`, `GENERIC_TIMEZONE`, `SCRAPER_PROVIDER`, `APIFY_TOKEN`, `ENRICHMENT_PROVIDER`, `APOLLO_API_KEY`, `CRM_PROVIDER`, `HUBSPOT_PRIVATE_APP_TOKEN`, `TWENTY_API_URL`, `TWENTY_API_KEY`, `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI`, `LINKEDIN_ORG_ID` |
| 9 | Prune automático de ejecuciones de n8n a 7 días (`EXECUTIONS_DATA_PRUNE=true`, `EXECUTIONS_DATA_MAX_AGE=168`) | `docker-compose.yml` servicio `n8n` | n8n no acumula historial infinito |

### B. Workflow 01 — Radar scrape (captura en Google Maps)

| # | Función | Dónde vive | Entradas → Salidas |
|---|---|---|---|
| 10 | Triple trigger: Manual + Schedule (cron `0 6 * * 1`, lunes 6:00) + Webhook `POST /webhook/radar-01` | `n8n/workflows/01-radar-scrape.json` nodos 1–3 | Disparo → inicia la cadena de captura |
| 11 | Armar búsquedas: genera 6 combinaciones = 3 queries × 2 corredores, `max_results: 40` c/u. Queries: `bodegas`, `centros logísticos`, `plantas industriales`. Corredores: `Toluca, Estado de México`, `Querétaro, Querétaro` (editables en el nodo para ampliar cobertura) | `01` nodo Code «Armar búsquedas» | — → 6 items `{query, location, max_results}` |
| 12 | Llamada al microservicio scraper por cada combinación (timeout 180 s) | `01` nodo HTTP «Scrapear Maps» | `POST http://scraper:5000/scrape` con `{query, location, max_results}` → `{ok, count, results[]}` |
| 13 | Normalizar respuestas: aplana resultados, **el `giro` del raw = la query de búsqueda** (no la categoría de Google), `fuente='google_maps'`, `query='query + location'`; dedup dentro del lote por `lower(nombre)\|lower(dirección)`; escapa comillas para SQL | `01` nodo Code «Normalizar» | Resultados del scraper → filas listas para INSERT |
| 14 | Guardar en `leads_raw` (con `procesado=false` por default) | `01` nodo Postgres «Guardar en raw» | Filas normalizadas → `INSERT INTO leads_raw (nombre, giro, direccion, lat, lng, telefono, web, rating, fuente, query)` |
| 15 | Cierre de corrida: inserta `runs(stage='radar-01', estado='ok', detalle={"origen":"n8n"})` — es la fila que **desbloquea la etapa 02** en el dashboard | `01` nodo Postgres «Run OK» (credencial «Postgres Radar») | Fin del workflow → fila en bitácora |

### C. Microservicio scraper (dual local/nube, mismo contrato REST)

| # | Función | Dónde vive | Entradas → Salidas |
|---|---|---|---|
| 16 | `GET /health` del scraper | `scraper/app.py` `health()` | → `{ok, servicio:'scraper', mode, provider, apify_token: bool}` |
| 17 | `POST /scrape` — contrato único para ambos backends | `scraper/app.py` `scrape()` | Entrada `{query*, location, max_results}` (default 40, clamp 1–60; sin `query` → 400) → `{ok, query, location, backend, count, results:[{nombre, direccion, telefono, web, rating, lat, lng, url}]}`; error de backend → 502 |
| 18 | Resolución de backend por request leyendo la tabla `providers` (`name='scraper'`): `mode=cloud`+`provider=apify` → Apify; si no → Playwright. Caché de 60 s. Override por env `SCRAPER_PROVIDER` (local/apify). Sin reiniciar nada | `scraper/app.py` `resolver_backend()` | Tabla `providers` → backend activo |
| 19 | Backend local Playwright: abre `google.com/maps/search/{query+location}`, cierra banners de cookies («Aceptar todo»/«Accept all»/«Cerrar»), hasta 3 rondas de scroll del feed (6 scrolls por ronda) recolectando enlaces `/maps/place/` hasta `max_results` | `scraper/app.py` `scrape_local()` | Búsqueda → lista de fichas a visitar |
| 20 | Extracción por ficha (best-effort, una ficha fallida NO tumba la corrida): nombre = `h1`; dirección = `button[data-item-id="address"]`; teléfono = `button[data-item-id*="phone:tel:"]` (o regex `tel:` del atributo); web = `a[data-item-id="authority"]`; rating = regex sobre `div[aria-label*="estrellas"]`; lat/lng = regex `@lat,lng` de la URL | `scraper/app.py` `scrape_local()` | Ficha de Google Maps → `{nombre, direccion, telefono, web, rating, lat, lng, url}` |
| 21 | Backend nube Apify: actor `apify/google-maps-scraper` (`searchStringsArray=[query+location]`, `maxCrawledPlacesPerSearch`, `language=es`, `countryCode=mx`); poll de estado cada 5 s hasta 48 veces (~4 min); mapea `title/address/phone/website/totalScore/location.lat/lng/url` al mismo esquema de salida. Sin `APIFY_TOKEN` → error explícito | `scraper/app.py` `scrape_apify()` | Mismo contrato que #17 |
| 22 | Uso responsable anti-bloqueo: delays aleatorios 2–5 s entre acciones (1.5–3 s y 2–4 s en scrolls), máx. 3 páginas por búsqueda, user-agent de Chrome 126, locale `es-MX`; si hay CAPTCHA la corrida trae menos resultados pero no truena ni escribe basura | `scraper/app.py` `pausa()` + `scraper/README.md` | — |

### D. Workflow 02 — Dedup + score (+ enriquecimiento Apollo opcional)

| # | Función | Dónde vive | Entradas → Salidas |
|---|---|---|---|
| 23 | Doble trigger (sin cron propio): Manual + Webhook `POST /webhook/radar-02`. Corre «tras la 01» | `n8n/workflows/02-dedup-score.json` nodos 1–2 | Disparo → inicia curaduría |
| 24 | **Dedup SQL atómico**: `INSERT INTO leads … SELECT … FROM leads_raw WHERE procesado=false AND NOT EXISTS (SELECT 1 FROM leads WHERE lower(nombre) y lower(direccion) coinciden)`, apoyado en `UNIQUE(nombre, direccion)` | `02` nodo Postgres «Insertar con dedup» | `leads_raw` sin procesar → leads nuevos en `leads` (sin duplicar) |
| 25 | **Score base al insertar**: +15 si el lead tiene web (`web <> ''`); +20 si el giro matchea logístico/industrial (ver regla R2). Score inicial = 0, 15, 20 o 35 | `02` nodo «Insertar con dedup» (CASE en el SELECT) | Lead nuevo → `score` base, `linea_recomendada='evaporativa'` provisional, `etapa='nuevo'` |
| 26 | **Sector derivado del giro** al insertar (ver regla R3) | `02` nodo «Insertar con dedup» (CASE) | `giro` → `sector` ∈ {logística, manufactura, otro} |
| 27 | Selección de leads a enriquecer con clima: `temp_zona IS NULL AND lat IS NOT NULL ORDER BY id LIMIT 60` por corrida | `02` nodo Postgres «Leads sin temperatura» | → hasta 60 leads por corrida |
| 28 | Temperatura actual por lead vía Open-Meteo (`GET api.open-meteo.com/v1/forecast?latitude&longitude&current=temperature_2m`, sin key, timeout 30 s) | `02` nodo HTTP «Open-Meteo» | lat/lng → `temperature_2m` actual |
| 29 | **Bonus por calor + línea por mes**: +20 si temp > 30 °C; línea recomendada según mes y giro (ver reglas R4–R5) | `02` nodo Code «Score y línea» | Lead + temp → `{id, temp, bonus, linea}` |
| 30 | Actualización del lead: `temp_zona = temp`, `score = LEAST(score + bonus, 100)`, `linea_recomendada = linea`, `updated_at = now()` | `02` nodo Postgres «Actualizar lead» | Lead curado con clima, score y línea |
| 31 | Lectura del provider de enriquecimiento (`SELECT mode, provider FROM providers WHERE name='enrichment'`); si falla, `onError: continue` (el pipeline sigue sin enriquecer) | `02` nodo Postgres «Leer provider enrichment» | → decide si corre la rama Apollo |
| 32 | Rama Apollo — gate: solo si `mode='cloud'` **Y** `provider='apollo'`; si no, salta directo a Consolidar | `02` nodo IF «¿Apollo activo?» | — |
| 33 | Rama Apollo — selección: top 20 leads por score con web no vacía y `enriquecido_apollo=false` (`ORDER BY score DESC LIMIT 20`) | `02` nodo Postgres «Top 20 con web» | → máx. 20 leads/corrida (1 crédito Apollo c/u) |
| 34 | Rama Apollo — extracción de dominio desde la web (quita protocolo, `www.` y path, minúsculas) | `02` nodo Code «Extraer dominio» | `web` → `domain` |
| 35 | Rama Apollo — enriquecimiento de organización: `POST https://api.apollo.io/api/v1/organizations/enrich` (credencial Header Auth «Apollo API», header `x-api-key`); `onError: continue` (key inválida no truena el pipeline) | `02` nodo HTTP «Apollo org enrich» | Dominio → datos de la organización (empleados) |
| 36 | Rama Apollo — bonus por empleados: ≥200 → +15; ≥50 → +10; <50 o sin dato → 0 (usa `estimated_num_employees` o `num_employees`) | `02` nodo Code «Merge Apollo» | Organización → `{id, empleados, bonus}` |
| 37 | Rama Apollo — guardar: `empleados = COALESCE(nuevo, actual)`, `score = LEAST(score + bonus, 100)`, `enriquecido_apollo = true` | `02` nodo Postgres «Guardar enrich» | Lead enriquecido |
| 38 | Idempotencia entre corridas: `UPDATE leads_raw SET procesado = true WHERE procesado = false` | `02` nodo Postgres «Marcar raw procesados» | Raw ya curado no se reprocesa |
| 39 | Cierre de corrida: `runs('radar-02','ok',{"origen":"n8n"})` — desbloquea 03 y 04 | `02` nodo Postgres «Run OK» | → fila en bitácora |

### E. Workflow 03 — Caza señales (manuales + cálidas)

| # | Función | Dónde vive | Entradas → Salidas |
|---|---|---|---|
| 40 | Triple trigger: Manual + Schedule (cron `0 7 * * *`, diario 7:00) + Webhook `POST /webhook/radar-03` | `n8n/workflows/03-signal-catcher.json` nodos 1–3 | Disparo → procesa señales |
| 41 | Lectura de `signals/input.json` (volumen compartido `/signals/input.json`) | `03` nodo Read Binary File «Leer signals/input.json» | JSON del SDR → items |
| 42 | Parseo de señales: formato `[{empresa, giro, tipo, evidencia, fecha}]`; arma `evidencia = tipo + ' — ' + evidencia` | `03` nodo Code «Parsear señales» | → filas `{nombre, giro, evidencia}` |
| 43 | **Upsert +25 por señal manual**: si la empresa no existe como lead, la CREA (score 25, `direccion=''`, etapa `nuevo`, línea `evaporativa`, sector `otro`); si existe, `score = LEAST(score+25, 100)` vía `ON CONFLICT (nombre, direccion)` (ver regla R6, incluye el detalle de que la etapa se pone en `nuevo`) | `03` nodo Postgres «Upsert +25» | Señal → lead creado o +25 |
| 44 | Lectura de señales cálidas pendientes: `SELECT id, titulo, detalle, empresa_ref FROM warm_signals WHERE procesada=false ORDER BY id LIMIT 50` (nodos con `onError: continue`: si la tabla no existe, el flujo sigue) | `03` nodo Postgres «Leer warm signals» | → warm signals sin procesar |
| 45 | Armado warm: solo señales con `empresa_ref` no vacía; `nombre = empresa_ref` | `03` nodo Code «Armar warm» | Warm signal → fila de upsert |
| 46 | **Upsert +25 por señal cálida** (mismo SQL que #43) | `03` nodo Postgres «Upsert warm +25» | Señal cálida → lead creado o +25 |
| 47 | Marcado: `UPDATE warm_signals SET procesada = true WHERE procesada = false` | `03` nodo Postgres «Marcar warm procesadas» | Warm signals procesadas no se re-aplican |
| 48 | Cierre: `runs('radar-03','ok',{"origen":"n8n"})` + nodo Set «Resumen» (`stage=radar-03`, nota «Señales de signals/input.json procesadas (+25 score)») | `03` nodos «Run OK» y «Resumen» | → fila en bitácora |

### F. Workflow 04 — Sync CRM espejo (HubSpot / Twenty)

| # | Función | Dónde vive | Entradas → Salidas |
|---|---|---|---|
| 49 | Doble trigger: Manual + Webhook `POST /webhook/radar-04`. **En v1 se importa pero queda INACTIVO** hasta migrar el CRM a la nube | `n8n/workflows/04-crm-sync.json` nodos 1–2 + `README.md` | Disparo → sync espejo |
| 50 | Lectura del provider CRM (`SELECT mode, provider FROM providers WHERE name='crm'`) + gate: si `mode != 'cloud'` → rama «Fin local» (no-op: «Postgres + dashboard es la fuente de verdad») y aun así registra Run OK | `04` nodos «Leer provider crm», IF «¿Nube activa?», Code «Fin local» | — |
| 51 | Selección de leads a sincronizar: `crm_synced_at IS NULL OR updated_at > crm_synced_at ORDER BY score DESC LIMIT 100` | `04` nodo Postgres «Leads para sync» | → máx. 100 leads/corrida |
| 52 | Rama por backend: IF `provider='hubspot'` → HubSpot; si no → «Twenty stub» (ver #55) | `04` nodo IF «¿HubSpot?» | — |
| 53 | Payload HubSpot (companies): `name, website, phone, address` + propiedades custom `biokool_etapa`, `biokool_score` (como string), `biokool_linea` | `04` nodo Code «Preparar payload» | Lead → body JSON |
| 54 | Upsert en HubSpot: `POST https://api.hubapi.com/crm/v3/objects/companies` (credencial Header Auth «HubSpot», `Authorization: Bearer <token>`; `onError: continue`). Requiere crear UNA vez en HubSpot las 3 propiedades de empresa `biokool_etapa`, `biokool_score`, `biokool_linea` (scope del Private App: `crm.objects.companies.write`) | `04` nodo HTTP «HubSpot upsert» | Lead → company en HubSpot |
| 55 | Marcaje de sincronizados: solo los leads cuya respuesta de HubSpot trae `id` (IF «¿OK?») → `UPDATE leads SET crm_synced_at = now() WHERE id IN (…)` (reconstruye ids por `pairedItem`) | `04` nodos Code «Marcar sync» + Postgres «Ejecutar marcaje» | Leads espejados marcados |
| 56 | **Twenty stub**: nodo Code que devuelve nota «conector pendiente de implementar (fase 2)» — punto de inserción oficial para Twenty CRM (open-source, self-hosted) | `04` nodo Code «Twenty stub» | — |
| 57 | Cierre: `runs('radar-04','ok',{"origen":"n8n"})` (todas las ramas convergen aquí) | `04` nodo Postgres «Run OK» | → fila en bitácora |

### G. Workflow 05 — Señales LinkedIn (monitoreo de TU página)

| # | Función | Dónde vive | Entradas → Salidas |
|---|---|---|---|
| 58 | Triple trigger: Manual + Schedule (cron `0 8 * * 1`, lunes 8:00) + Webhook `POST /webhook/radar-05` | `n8n/workflows/05-linkedin-signals.json` nodos 1–3 | Disparo → monitoreo de página |
| 59 | Lectura de config LinkedIn (`SELECT mode, config FROM providers WHERE name='linkedin'`); gate IF `mode='cloud'`, si no → «Fin (inactivo)» → Run OK (nunca truena) | `05` nodos «Leer config linkedin», IF «¿Activo?», Code «Fin (inactivo)» | — |
| 60 | Chequeo de token: vigente si existe `access_token` y `expires_at` no venció (margen 60 s). Motivos de fallo explícitos: sin token / falta `org_id` / token expirado | `05` nodo Code «Checar token» | → `{token, org_id, vigente, motivo}` |
| 61 | Aviso de reconexión: si el token no es válido, inserta en `warm_signals` una señal `('linkedin', 'LinkedIn: reconexión necesaria', motivo)` y cierra con Run OK en vez de fallar | `05` nodos Code «Aviso token» + Postgres «Insertar aviso» | Problema de token → aviso visible |
| 62 | Stats previas: último `followers` de `linkedin_stats` (para calcular el delta) | `05` nodo Postgres «Stats previas» | → seguidores anteriores |
| 63 | Seguidores actuales: `GET https://api.linkedin.com/v2/networkSizes/urn:li:organization:{org_id}?edgeType=COMPANY_FOLLOWED_BY_MEMBER` → `firstDegreeSize` (headers: `Authorization: Bearer`, `Linkedin-Version: 202601`, `X-Restli-Protocol-Version: 2.0.0`) | `05` nodo HTTP «Stats seguidores» | → seguidores actuales |
| 64 | Posts recientes: `GET https://api.linkedin.com/rest/posts?author=urn:li:organization:{org_id}&count=10&sortBy=CREATED` | `05` nodo HTTP «Posts recientes» | → últimos 10 posts |
| 65 | Engagement por post: para los **top 5 URNs** de posts → `GET /rest/socialActions/{urn}/likes?count=1` y `/comments?count=1` → usa `paging.total` de cada uno | `05` nodos Code «Top 5 URNs», HTTP «Likes», Code «Juntar likes», HTTP «Comments», Code «Juntar todo» | → `{urn, likes, comments}` por post |
| 66 | **Detección de señales cálidas** (umbrales exactos en regla R9): señal si seguidores nuevos ≥ 3; señal por cada post con likes+comentarios ≥ 5 (incluye link al post) | `05` nodo Code «Detectar señales» | Stats + engagement → 0..n señales |
| 67 | Guardar stats del día: upsert en `linkedin_stats` por `UNIQUE(org_id, stats_date)` (`followers`, `posts_count` = posts evaluados, `engagement_total` = suma likes+comentarios de los top 5) | `05` nodo Postgres «Guardar stats» | → fila diaria de stats |
| 68 | Guardar señales en `warm_signals` (`fuente='linkedin'`, titulo, detalle) — las procesa la 03 con +25 (función #46) | `05` nodo Postgres «Guardar warm» | Señales → `warm_signals` pendientes |
| 69 | Cierre: `runs('radar-05','ok',{"origen":"n8n"})`. Prácticamente **todos los nodos de la 05 llevan `onError: continueRegularOutput`**: LinkedIn nunca truena el pipeline | `05` nodo Postgres «Run OK» + settings de nodos | → fila en bitácora |
| 70 | Alcance honesto documentado (sticky note + docs): la API de LinkedIn **NO permite buscar prospectos ni extraer contactos**; solo se monitorea la página propia (~12 requests por corrida semanal) | `05` sticky «Nota: alcance LinkedIn», `README.md`, `ARQUITECTURA.md`, guía §6 | — |

### H. API REST del dashboard (`dashboard/server.js`, base `:3000`)

| # | Función | Dónde vive | Entradas → Salidas |
|---|---|---|---|
| 71 | `GET /api/leads` — lista de leads ordenados por `score DESC, id DESC`; filtro opcional `?etapa=` validado contra las 6 etapas (valor inválido = sin filtro) | `server.js` ruta leads | → array de leads completos (todas las columnas) |
| 72 | `GET /api/leads/:id` — detalle de un lead (lo consume el drawer) | `server.js` | id → lead completo; 404 si no existe |
| 73 | `PATCH /api/leads/:id` — actualizar `etapa` (validada contra las 6, 400 si inválida) y/o `notas` (texto libre); actualiza `updated_at`; 400 si no se manda nada, 404 si no existe | `server.js` | `{etapa?, notas?}` → `{ok, lead}` actualizado |
| 74 | `GET /api/runs` — bitácora combinada: **locales** = últimos 30 de la tabla `runs`; **n8n** = últimas 20 ejecuciones vía API pública de n8n (`GET {N8N_BASE}/api/v1/executions?limit=20`, header `X-N8N-API-KEY`) mapeadas a `{workflow, estado, started, finished}`; sin `N8N_API_KEY` → `n8nError` (solo afecta lectura) | `server.js` ruta runs | → `{local:[], n8n:[]|null, n8nError}` |
| 75 | `POST /api/run/:stage` — ejecución manual EN ORDEN con **gating** (regla R10): 400 si stage ∉ 01–05; 409 con motivo diferenciado si la previa no está en `ok`; registra la corrida como `running` con `detalle={origen:'dashboard', manual:true}`; dispara el webhook de n8n con body `{source:'dashboard', stage, runId}`; si el webhook falla, marca la corrida `error` con el mensaje | `server.js` ruta run + `STAGES` | `:stage` → `{ok, mensaje, runId}` o error 409/500 |
| 76 | `GET /api/providers` — lista de providers enriquecida con el catálogo en código: `etiqueta`, descripción de la opción nube, `modos` válidos y `backends` válidos por provider (para pintar toggles/selects) | `server.js` ruta providers + constante `PROVIDERS` | → 6 providers con metadatos de UI |
| 77 | `PATCH /api/providers/:name` — cambiar `mode`, `provider` y/o `config`; valida contra el catálogo (400 provider/modo/backend inválido) y la **coherencia** (regla R11); `config` se **fusiona** con la existente (`config || nuevo`), no se reemplaza; responde el provider actualizado incl. `config` | `server.js` ruta providers | `{mode?, provider?, config?}` → `{ok, provider}` |
| 78 | `GET /api/workflows` — catálogo estático de las 5 etapas: `{stage, nombre, cron, descripcion}` (solo lectura; la fuente real de cron vive en n8n) | `server.js` constante `WORKFLOWS` | → 5 etapas con nombre/cron/descripción |
| 79 | `GET /api/config` — configuración SIN secretos: `version 'v1.1'`, `n8n` (URL base), `timezone`, presencia (booleanos) de los 5 webhooks y de `N8N_API_KEY`, y `cloudKeys: {apify, apollo, hubspot, linkedin}` solo como booleanos | `server.js` ruta config | → objeto de presencia, jamás valores |
| 80 | `GET /api/weather?lat=&lng=` — proxy a Open-Meteo con **caché en memoria de 6 h** (clave = lat,lng redondeados a 2 decimales): pide `current=temperature_2m` + `daily=temperature_2m_max` con `forecast_days=3`; 400 si lat/lng inválidos, 502 si Open-Meteo falla | `server.js` ruta weather + `climaCache` | lat/lng → `{ok, cached: bool, data}` |
| 81 | `GET /api/health` — diagnóstico/semáforo con 5 checks (detalle en vista Sistema, función #103): postgres (`SELECT 1`), providers (conteo de la tabla; error sugiere auto-migración), **cobertura de líneas** (conteo de leads por línea; `warn` y `ok=false` si alguna de koolkat/solar/evaporativa está en 0, incluye el objeto `cobertura`), n8n (`GET /healthz`, timeout 5 s), scraper (`GET /health`, timeout 5 s, reporta el backend activo) | `server.js` ruta health | → `{ok, checks:{…}, cobertura:{koolkat, solar, evaporativa}}` |
| 82 | `POST /api/signals` — el SDR registra un hallazgo: valida `empresa*` y `evidencia*` (400 si faltan), lee `signals/input.json`, **agrega** `{empresa, giro, tipo (default 'hallazgo'), evidencia, fecha=hoy}` y reescribe el archivo; responde `{ok, total, mensaje}` (la 03 lo procesa con +25) | `server.js` ruta signals + `SIGNALS_PATH` (env, default `/signals/input.json`) | `{empresa, giro, tipo, evidencia}` → señal persistida en el JSON |
| 83 | `GET /api/linkedin/auth` — inicia OAuth: redirige a `linkedin.com/oauth/v2/authorization` con `response_type=code` y scopes `openid profile r_organization_social r_organization_admin`; 400 si falta `LINKEDIN_CLIENT_ID` | `server.js` ruta linkedin/auth | → redirect a LinkedIn |
| 84 | `GET /api/linkedin/callback` — intercambia el `code` por tokens (`POST /oauth/v2/accessToken`, `grant_type=authorization_code`), los guarda en `providers.config` de linkedin fusionados (`access_token`, `refresh_token`, `expires_at`, `connected_at`) y pone el provider en `mode='cloud'`; muestra página HTML de confirmación «✓ LinkedIn conectado» | `server.js` ruta linkedin/callback | `?code=` → tokens guardados en Postgres |
| 85 | `GET /api/linkedin/status` — estado sin secretos: `{mode, provider, enabled, conectado, expira, expirado, org_id, tieneClientId, tieneClientSecret, stats[últimos 7 días de linkedin_stats], warmSignals[últimas 10 sin procesar]}` | `server.js` ruta linkedin/status | → estado para la tarjeta LinkedIn |
| 86 | `POST /api/linkedin/disconnect` — borra tokens (`config='{}'`) y pone el provider linkedin en `mode='disabled'` | `server.js` ruta linkedin/disconnect | → `{ok, mensaje}` |
| 87 | Servir la SPA: `express.static(public/)` en el puerto 3000 | `server.js` final | → dashboard web |

### I. Frontend del dashboard (`dashboard/public/`) — funciones transversales

| # | Función | Dónde vive | Entradas → Salidas |
|---|---|---|---|
| 88 | SPA de 5 vistas con navegación por botones `data-view` (Panel, Operación, Leads, Mapa, Sistema), título y subtítulo por vista (`VIEW_META`), menú móvil con hamburguesa + scrim | `index.html` + `app.js` `showView()` | Clic en menú → vista activa (carga sus datos) |
| 89 | Tema claro/oscuro con toggle en el header, persistido en `localStorage` (`radar-theme`, default `dark`); al cambiar, re-tematiza las gráficas ECharts y revalida el tamaño del mapa | `app.js` `initTheme()/toggleTheme()/refreshCharts()` + `index.html` `#themeBtn` | Preferencia → tema aplicado en toda la SPA |
| 90 | Indicador de conexión en el header (dot con pulso): verde si `GET /api/health` dice `ok`, rojo si hay problemas o no hay backend; tooltip explica el estado | `app.js` init + `#connDot` | Salud del sistema visible en todo momento |
| 91 | Badge con el total de leads en el ítem de menú «Leads» (se oculta si es 0) y dot de advertencia en el ítem «Sistema» cuando el health no es `ok` | `app.js` `loadPanel()`/`loadDiag()` + `index.html` `#navLeadsCount`, `#navSysWarn` | Estado resumido sin entrar a la vista |
| 92 | Sistema de toasts (éxito/error) con auto-cierre ~5.2 s | `app.js` `toast()` | Feedback de toda acción |
| 93 | Modal genérico reutilizable (título, cuerpo HTML, botones de acción) — se usa para: confirmar ejecución de etapa, registrar señal, confirmar desconexión de LinkedIn. Cierre con botón ✕, clic fuera o tecla Escape | `app.js` `openModal()/closeModal()` | — |
| 94 | **Polling suave cada 25 s**: si hay corridas en estado `running` y la vista actual es Operación o Panel, recarga esa vista automáticamente; se pausa si la pestaña no es visible (`document.hidden`) | `app.js` bloque «Polling suave» | La UI se actualiza sola durante las corridas largas |
| 95 | Normalización de teléfono MX para contacto: quita no-dígitos; 10 dígitos → prefijo `52`; 12 dígitos que empiezan `52` → tal cual; 11 que empiezan `1` → tal cual; ≥10 → tal cual; <10 → `null` (sin botones de llamada) | `app.js` `normPhone()` | `telefono` crudo → número listo para `tel:` y `wa.me` |
| 96 | Normalización de URL de sitio: agrega `https://` si falta protocolo | `app.js` `normWeb()` | `web` cruda → enlace abrible |
| 97 | Explicación en lenguaje simple de «por qué esta línea» por lead (`whyLinea`): Solar = temporada de planeación oct–feb (+ si el giro matchea `/gasolin\|estacionamiento\|comercial\|plaza\|tienda\|super/` menciona «tu sombra genera»); Koolkat = temporada de calor feb–jun (si aplica) / control térmico industrial; Evaporativa = confort todo el año. Nota: el regex de la explicación incluye `super` y el del workflow 02 no (ver R5) | `app.js` `whyLinea()` | Lead → texto «Por qué este lead» del drawer |

### J. Funciones documentadas como Fase 2 / diseño (existen en docs o esquema, sin implementar)

| # | Función | Dónde vive | Entradas → Salidas |
|---|---|---|---|
| 98 | Tabla `proposals` (propuestas por lead: `lead_id` FK con `ON DELETE CASCADE`, `titulo`, `linea`, `monto NUMERIC(12,2)`, `estado` default `borrador`): creada en el esquema pero **nadie la escribe ni la lee en v1**; es el gancho de fase 2 (cuando pida pipeline real → Twenty CRM) | `db/init.sql` + `docs/ARQUITECTURA.md` tabla de escritores | — (fase 2) |
| 99 | Provider `email` (kind `email`, `disabled` por default, backends `local`/`smtp`): apagado a propósito; fase 2 = email frío con **dominios dedicados** (nunca el corporativo `@biokool.mx`), warmup 4–6 semanas, SPF/DKIM/DMARC | `db/init.sql` seed + `server.js` `PROVIDERS.email` + `ARQUITECTURA.md` §Fase 2 | — (fase 2) |
| 100 | Automatizar señales: Google Alerts / scraping de noticias → `signals/input.json` sin intervención manual | `docs/ARQUITECTURA.md` §Fase 2 + doc técnica §11 | — (fase 2) |
| 101 | WhatsApp: API oficial + bot calificador (costo por conversación; evaluar tras el piloto) | `docs/ARQUITECTURA.md` §Fase 2 + doc técnica §11 | — (fase 2) |
| 102 | Calibración con datos reales: ajustar reglas de score y de línea con las tasas del piloto antes de gastar en providers nube | `docs/ARQUITECTURA.md` §Fase 2 | — (fase 2) |

---

## 2. Datos y filtros disponibles

### 2.1. Campos exactos por tabla (fuente: `db/init.sql` + auto-migración de `server.js`)

**`leads_raw`** — salida cruda del scraper (escribe: workflow 01; lee: workflow 02)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | SERIAL PK | |
| `nombre` | TEXT | Nombre del negocio en Google Maps |
| `giro` | TEXT | **Es la query de búsqueda** (`bodegas`, `centros logísticos`, `plantas industriales`), NO la categoría real de Google |
| `direccion` | TEXT | Dirección en **texto libre** tal como la da Google Maps |
| `lat`, `lng` | DOUBLE PRECISION | Extraídos de la URL de la ficha; pueden ser NULL |
| `telefono` | TEXT | Texto libre de la ficha |
| `web` | TEXT | URL del sitio |
| `rating` | DOUBLE PRECISION | Estrellas de Google (0–5) |
| `fuente` | TEXT | Default `'google_maps'` |
| `query` | TEXT | `query + location` de la búsqueda que lo encontró |
| `procesado` | BOOLEAN | Default FALSE; la 02 lo pone TRUE (idempotencia) |
| `created_at` | TIMESTAMPTZ | Default `now()` |

**`leads`** — base curada (escriben: 02, 03, dashboard vía PATCH; leen: dashboard, 02, 03, 04)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | SERIAL PK | |
| `nombre` | TEXT NOT NULL | |
| `giro` | TEXT | Heredado de la query (o de la señal) |
| `direccion` | TEXT | Default `''`; texto libre |
| `lat`, `lng` | DOUBLE PRECISION | NULL en leads creados por señales |
| `telefono` | TEXT | |
| `web` | TEXT | |
| `empleados` | INT | Solo lo llena Apollo (workflow 02) |
| `sector` | TEXT | Derivado: `logística` / `manufactura` / `otro` (regla R3) |
| `score` | INT | Default 0; siempre acotado 0–100 (regla R1) |
| `linea_recomendada` | TEXT + CHECK | ∈ {`koolkat`, `solar`, `evaporativa`} |
| `etapa` | TEXT + CHECK | ∈ {`nuevo`, `contactado`, `reunion`, `propuesta`, `ganado`, `perdido`}; default `nuevo` |
| `temp_zona` | DOUBLE PRECISION | Temperatura actual de la zona del lead (Open-Meteo); NULL = aún no procesado por la 02 |
| `enriquecido_apollo` | BOOLEAN | Default FALSE (columna de capa providers) |
| `crm_synced_at` | TIMESTAMPTZ | Última sync exitosa a CRM (workflow 04) |
| `notas` | TEXT | Default `''`; notas libres del SDR (PATCH) |
| `created_at`, `updated_at` | TIMESTAMPTZ | |
| — | UNIQUE(`nombre`, `direccion`) | Llave de dedup y de los upserts +25 |

**`runs`** — bitácora de ejecuciones (escriben: dashboard al disparar y al fallar, workflows al terminar OK; lee: dashboard para gating y bitácora)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | SERIAL PK | |
| `stage` | TEXT NOT NULL | `radar-01` … `radar-05` (o `manual` según comentario del esquema) |
| `estado` | TEXT + CHECK | ∈ {`running`, `ok`, `error`} |
| `detalle` | JSONB | `{origen:'dashboard', manual:true}` al disparar; `{origen:'n8n'}` al cerrar OK; `{error: '…'}` al fallar |
| `started_at`, `finished_at` | TIMESTAMPTZ | |

**`providers`** — capa anti-cautiverio (escribe: dashboard vía PATCH, seed en init/migración; leen: scraper por request, workflows 02/04/05 al inicio de su rama, dashboard)

| Campo | Tipo | Notas |
|---|---|---|
| `name` | TEXT PK | ∈ {`scraper`, `enrichment`, `crm`, `email`, `weather`, `linkedin`} |
| `kind` | TEXT NOT NULL | `scrape` / `enrich` / `crm` / `email` / `weather` / `signals` |
| `mode` | TEXT + CHECK | ∈ {`local`, `cloud`, `disabled`}; defaults: scraper/enrichment/crm `local`, email/linkedin `disabled`, weather `cloud` |
| `provider` | TEXT NOT NULL | Backend: `local`, `apify`, `apollo`, `hubspot`, `twenty`, `smtp`, `open-meteo`, `linkedin` según capacidad |
| `config` | JSONB | Default `'{}'`; en linkedin guarda `access_token`, `refresh_token`, `expires_at`, `connected_at`, `org_id` |
| `enabled` | BOOLEAN | Default TRUE |
| `updated_at` | TIMESTAMPTZ | |

**`linkedin_stats`** — métricas diarias de la página (escribe/lee: workflow 05; lee: dashboard status)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | SERIAL PK | |
| `org_id` | TEXT | ID numérico de la página |
| `followers` | INT | `firstDegreeSize` de la API |
| `posts_count` | INT | Posts evaluados en la corrida (top 5 con engagement medido) |
| `engagement_total` | INT | Suma de likes + comentarios de los top 5 posts |
| `stats_date` | DATE | Default `CURRENT_DATE`; UNIQUE(`org_id`, `stats_date`) |
| `raw` | JSONB | (declarada; la 05 no la llena) |
| `created_at` | TIMESTAMPTZ | |

**`warm_signals`** — señales cálidas (escribe: workflow 05 y avisos de token; leen: workflow 03 y dashboard status)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | SERIAL PK | |
| `fuente` | TEXT NOT NULL | Default `'linkedin'` |
| `titulo` | TEXT | Ej. «LinkedIn: +5 seguidores nuevos» |
| `detalle` | TEXT | Texto explicativo (puede traer el link del post) |
| `empresa_ref` | TEXT | Empresa a la que aplicar el +25 (match con `leads.nombre` vía upsert); **NULL/vacío en señales de página** (la 03 las salta: no hay empresa a cuál sumar) |
| `procesada` | BOOLEAN | Default FALSE; la 03 la pone TRUE |
| `created_at` | TIMESTAMPTZ | |

**`proposals`** — fase 2, sin uso en v1: `id` SERIAL PK, `lead_id` INT FK→`leads(id)` ON DELETE CASCADE, `titulo` TEXT, `linea` TEXT, `monto` NUMERIC(12,2), `estado` TEXT default `'borrador'`, `created_at` TIMESTAMPTZ.

**`signals/input.json`** — archivo (volumen `./signals`, n8n lo monta `:ro`, el dashboard lectura/escritura): array de objetos `{empresa, giro, tipo, evidencia, fecha}`. Tipos usados en la UI: `hallazgo`, `ampliación`, `cambio de gerente`, `licitación`, `nota de prensa`, `otro`.

### 2.2. Matriz de filtros REALES (dónde se puede filtrar y por qué campo)

| Superficie | Filtro | Campo(s) | Cómo |
|---|---|---|---|
| API `GET /api/leads?etapa=` | Etapa | `leads.etapa` (6 valores, validado) | Query param; único filtro de la API de leads |
| Vista Leads — buscador | Texto libre | `nombre` + `giro` + `direccion` (concatenados, `includes`, insensible a mayúsculas, con debounce 220 ms) | Cliente, sobre los leads ya cargados |
| Vista Leads — select | Etapa | `leads.etapa` | Cliente (además del filtro API) |
| Vista Leads — select | Línea recomendada | `leads.linea_recomendada` (koolkat/solar/evaporativa) | Cliente |
| Vista Mapa — select | Línea recomendada | `leads.linea_recomendada` | Cliente; solo pinta leads con `lat/lng` no nulos |
| Vista Mapa — select | Etapa | `leads.etapa` | Cliente; idem |
| Vista Mapa — checkbox | Capa de temperatura (on/off) | `leads.temp_zona` | Muestra/oculta la capa de círculos térmicos |
| Workflow 02 (interno) | Sin temperatura, con coordenadas, orden por id, tope 60 | `temp_zona IS NULL AND lat IS NOT NULL` | SQL |
| Workflow 02 Apollo (interno) | Con web, no enriquecidos, orden score desc, tope 20 | `web <> '' AND enriquecido_apollo = false` | SQL |
| Workflow 03 (interno) | Warm signals sin procesar, tope 50 | `warm_signals.procesada = false` | SQL |
| Workflow 04 (interno) | Sin sincronizar o modificados tras el sync, orden score desc, tope 100 | `crm_synced_at IS NULL OR updated_at > crm_synced_at` | SQL |
| Dashboard bitácora (interno) | Últimas 30 corridas locales / 20 ejecuciones n8n | `runs` / API n8n | SQL / API |

**Ordenamientos fijos:** leads siempre `score DESC, id DESC` (API); bitácora `id DESC`; stats de LinkedIn `stats_date DESC`; warm signals pendientes `id DESC`.

### 2.3. ⚠️ Lo que NO existe en el Radar (crítico para no prometerlo en la Sección 2)

En **ninguna** tabla, vista, filtro ni workflow del repo existen campos estructurados de:

- **Entidad / estado** — no hay columna; el «corredor» vive solo como texto `location` en las búsquedas del workflow 01 (`Toluca, Estado de México`, `Querétaro, Querétaro`) y dentro de la `direccion` en texto libre.
- **Municipio** — no existe como campo ni filtro.
- **Colonia** — no existe como campo ni filtro.
- **Código postal** — no existe como campo ni filtro.
- **SCIAN** — no existe en todo el repo (ni columna, ni catálogo, ni mapeo giro→SCIAN). El `giro` es la query de búsqueda en texto libre y el `sector` es una derivación por regex con solo 3 valores.

Lo único geográfico filtrable hoy es: texto libre sobre `direccion` (buscador de Leads), `lat/lng` (presencia en el mapa) y `temp_zona`. Si la Sección 2 requiere filtros por entidad/municipio/colonia/CP/SCIAN, hay que **derivarlos** (parsear la dirección de Google o geocodificar) o **capturarlos** como campos nuevos: no vienen del Radar.

---

## 3. Reglas de negocio

### Scoring (score siempre entero, acotado a 100 con `LEAST(…, 100)` en cada suma)

- **R1 — Tope universal:** ninguna suma puede pasar de 100 (`LEAST(score + bonus, 100)` en 02, 03 y Apollo). No hay piso explícito (los bonos nunca son negativos).
- **R2 — Score base (workflow 02, al insertar):**
  - **+15** si el lead tiene sitio web (`web IS NOT NULL AND web <> ''`).
  - **+20** si el giro matchea logístico/industrial: `lower(giro) LIKE '%log%' OR '%plant%' OR '%industr%'`.
  - Score inicial posible: 0, 15, 20 o 35. Línea provisional al insertar: `evaporativa`; etapa: `nuevo`.
- **R3 — Sector derivado (workflow 02, al insertar):** `giro LIKE '%log%'` → `logística`; si no, `giro LIKE '%plant%' OR '%industr%' OR '%bodeg%' OR '%cedis%'` → `manufactura`; si no → `otro`.
- **R4 — Bonus por clima (workflow 02):** temperatura actual de la zona del lead (Open-Meteo) **> 30 °C → +20**. Con 30.0 °C exactos NO hay bonus (es `>` estricto). Solo se calcula para leads con `temp_zona IS NULL` y coordenadas (tope 60/corrida); un lead ya procesado **no** recalcula temperatura, bonus ni línea en corridas posteriores.
- **R5 — Línea recomendada por mes (workflow 02, nodo «Score y línea»; `m` = mes 0–11 de `new Date().getMonth()`):**
  - **feb–jun** (`m` ∈ 1..5) → `koolkat` para todos (temporada de calor; ángulo: bajar OPEX eléctrico / urgencia térmica).
  - **oct–feb** (`m` ≥ 9 **o** `m` ≤ 1) → `solar` **solo si** el giro matchea la regex `/gasolin|estacionamiento|comercial|plaza|tienda/`; si no matchea → `evaporativa`. (Ángulo solar: «tu sombra genera» — canopies que dan sombra y producen; el cliente planea capex en invierno.)
  - **jul–sep** (`m` ∈ 6..8) → `evaporativa` para todos (funciona todo el año; ángulo: confort + productividad + aire fresco, sin obra mayor).
  - Nota de implementación: febrero cae en ambas ramas del código; gana `koolkat` porque su rama se evalúa primero. La explicación de UI (`whyLinea`, #97) usa una regex de giro apto para solar ligeramente distinta: incluye `super` (`/gasolin|estacionamiento|comercial|plaza|tienda|super/`).
- **R6 — Señales +25 (workflow 03):** cada señal (manual de `input.json` o cálida con `empresa_ref`) hace upsert por `UNIQUE(nombre, direccion)`:
  - Si el lead no existe → se crea con **score 25**, `direccion=''`, etapa `nuevo`, línea `evaporativa`, sector `otro` (las señales manuales conservan su `giro`; las cálidas crean con `giro=''`).
  - Si existe → `score = LEAST(score + 25, 100)` **y `etapa` se pone en `'nuevo'`** (el SQL del upsert lo incluye literalmente: una señal «reactiva» el lead aunque estuviera avanzado — comportamiento real del código, a conservar o corregir conscientemente).
  - Las señales manuales **no se marcan como procesadas en ningún lado**: cada corrida de la 03 vuelve a aplicar +25 por cada señal que siga en `input.json` (así está escrito; solo las `warm_signals` tienen bandera `procesada`).
- **R7 — Bonus Apollo (workflow 02, rama opcional):** empleados ≥ 200 → **+15**; 50–199 → **+10**; < 50 o sin dato → 0. Solo top 20 por corrida (orden score desc, con web, no enriquecidos), 1 crédito por empresa, y el lead queda marcado `enriquecido_apollo=true` (no se vuelve a cobrar).
- **R8 — Dedup:** la identidad de un lead es `(nombre, direccion)` — `UNIQUE` en BD + `NOT EXISTS` con `lower()` en ambos campos al insertar (02) + dedup en lote por `lower(nombre|direccion)` al normalizar (01). Los duplicados «se eliminan solos» entre corridas.
- **R9 — Detección de señales cálidas LinkedIn (workflow 05):**
  - Seguidores nuevos = `firstDegreeSize` actual − último `followers` guardado; **≥ 3 → señal** «LinkedIn: +N seguidores nuevos» («Publica y prospecta esta semana»).
  - Post con **likes + comentarios ≥ 5** (entre los top 5 posts recientes) → señal con el conteo y el link `linkedin.com/feed/update/{urn}` («Quienes interactúan son leads cálidos»).
  - Engagement total del día = suma de likes+comentarios de los top 5 posts.
  - Estas señales de página tienen `empresa_ref` vacío → la 03 las marca procesadas **sin** sumar a ningún lead (el +25 aplica solo cuando la señal trae empresa, típicamente las manuales o avisos con match por nombre).
- **R10 — Gating de corridas (dashboard, `POST /api/run/:stage` + constante `STAGES`):**
  - Orden obligatorio: **02 requiere `radar-01` en `ok`**; **03 requiere `radar-02` en `ok`**; **04 requiere `radar-02` en `ok`**; **01 y 05 no requieren nada**.
  - El chequeo mira la **última** fila de `runs` de la etapa previa. Si no está en `ok` → **409** con motivo diferenciado: *nunca* («nunca se ha ejecutado, ejecútala primero»), *running* («sigue en ejecución desde {fecha}… si se atoró, revísala en n8n → Executions»), *error* («terminó en error. Último detalle: {detalle.error}»).
  - La misma regla se refleja en la UI de Operación (botón deshabilitado + motivo con 🔒).
  - Cada disparo crea su fila `running`; el workflow al terminar inserta **otra** fila `ok` (la fila `running` del dashboard no se actualiza a `ok`: la bitácora muestra ambas; el «último estado» de cada etapa es la fila más reciente).
- **R11 — Coherencia de providers (`PATCH /api/providers/:name`):** `mode='cloud'` exige backend nube (≠ `local`); `mode='local'` exige `provider='local'`. Modos/backends permitidos por capacidad (constante `PROVIDERS` en `server.js`):
  - `scraper`: modos {local, cloud}; backends {local, apify}.
  - `enrichment`: modos {local, cloud}; backends {local, apollo}.
  - `crm`: modos {local, cloud}; backends {local, hubspot, twenty}.
  - `email`: modos {disabled, cloud}; backends {local, smtp}.
  - `weather`: modos {cloud}; backends {open-meteo}.
  - `linkedin`: modos {disabled, cloud}; backends {linkedin}.
- **R12 — El núcleo nunca depende de la nube:** si un provider nube falla (key inválida, cuota), el pipeline sigue en local o salta la rama — los nodos nube llevan `onError: continueRegularOutput` (Apollo en 02; ramas de warm signals en 03; HubSpot en 04; casi toda la 05). Los datos **siempre aterrizan primero en Postgres**; HubSpot/Twenty son espejos de visualización, nunca el sistema de registro.
- **R13 — Clima en el dashboard:** proxy con caché de **6 horas** por coordenada redondeada a 2 decimales (Open-Meteo gratis: 10k req/día). La capa de temperatura del mapa dibuja un círculo rojo por lead con radio `max(2500, (temp_zona − 18) × 1800)` metros (más grande = más calor).
- **R14 — Cobertura de líneas (health):** si alguna de las 3 líneas (koolkat/solar/evaporativa) tiene **0 leads**, el diagnóstico marca `warn` y el health global `ok=false`, con la recomendación «corre la 01/02 o revisa la regla de línea por mes». La misma condición genera una alerta en el Panel.
- **R15 — Principio comercial (docs):** «el Radar propone, tú decides» — el sistema **nunca envía mensajes ni contacta clientes solo**; la automatización está en detección, orden y seguimiento. Señales > volumen: no se compran bases ni se manda frío en masa.
- **R16 — Email frío (regla de fase 2, ya documentada):** jamás desde el dominio corporativo (`@biokool.mx`): quema su reputación y afecta cotizaciones/facturación. Dominios dedicados tipo `biokool-ventas.com`, warmup 4–6 semanas, SPF/DKIM/DMARC; el correo corporativo se reserva para prospectos ya interesados.
- **R17 — ICP y calendario comercial (doc técnica §1):** empresas B2B en corredores industriales de México con superficies amplias (techos, estacionamientos, naves) y consumo eléctrico relevante. Koolkat: manufactura/CEDIS/granjas, fuerte feb–jun. Evaporativa: naves, gimnasios, restaurantes, cocinas, talleres, todo el año. Solar: gasolineras al aire libre, estacionamientos, plazas, naves con techos amplios, fuerte oct–feb.

### Límites y topes (todos los del sistema)

| Tope | Valor | Dónde |
|---|---|---|
| Score máximo | 100 (`LEAST`) | 02, 03, Apollo |
| Resultados por búsqueda del scraper | default 40, clamp 1–60 | `scraper/app.py` |
| Páginas de resultados por búsqueda | 3 rondas de scroll (6 scrolls c/u) | `scraper/app.py` |
| Búsquedas por corrida de la 01 | 6 (3 queries × 2 corredores) | workflow 01 |
| Leads con clima por corrida de la 02 | 60 | workflow 02 SQL |
| Leads Apollo por corrida | 20 | workflow 02 SQL |
| Warm signals leídas por corrida de la 03 | 50 | workflow 03 SQL |
| Leads a CRM por corrida de la 04 | 100 | workflow 04 SQL |
| Posts de LinkedIn por corrida de la 05 | 10 recientes; engagement de los top 5 | workflow 05 |
| Bitácora local mostrada | últimas 30 corridas | `GET /api/runs` |
| Ejecuciones de n8n mostradas | últimas 20 | `GET /api/runs` |
| Stats LinkedIn en status | últimos 7 días | `GET /api/linkedin/status` |
| Warm signals pendientes en status | últimas 10 | `GET /api/linkedin/status` |
| Caché de clima (dashboard) | 6 h | `server.js` |
| Caché de provider (scraper) | 60 s | `scraper/app.py` |
| Requests LinkedIn por corrida | ~12 (muy por debajo del rate limit) | doc técnica §7 |

---

## 4. Vistas del dashboard original (las 5, en detalle)

Navegación lateral con 5 vistas (`panel`, `operacion`, `leads`, `mapa`, `sistema`), header con título/subtítulo por vista, dot de conexión y toggle de tema. Fuentes: `dashboard/public/index.html` y `app.js`.

### 4.1. Panel — «Vista ejecutiva: cómo van tus leads hoy»

- **Alertas accionables** (sección superior, cada una con botón que navega a la vista que la resuelve):
  1. *Sin leads aún* (info) → botón «Ir a Operación».
  2. *Sin leads para: {líneas en 0}* (warn, desde `health.cobertura`) → «Ir a Operación».
  3. *N errores esta semana* (err; cuenta runs en `error` de los últimos 7 días y muestra el detalle del más reciente) → «Ver en Sistema».
  4. *Token de LinkedIn expirado* (warn, desde `linkedin/status.expirado`) → «Ver en Sistema».
- **4 KPI cards:** *Leads totales* (sub: «N nuevos por trabajar»), *Score promedio* (media de score, «de 100»), *Oportunidades* (reunión + propuesta), *Ganados* (sub: «N perdidos»).
- **Gráfica «Embudo de conversión»** (ECharts funnel): Nuevo → Contactado → Reunión → Propuesta → Ganado (sin Perdido).
- **Gráfica «Leads por línea recomendada»** (ECharts dona con %): Koolkat / Solar / Evaporativa con sus colores.
- **Gráfica «Distribución de score»** (barras): buckets 0–20, 21–40, 41–60, 61–80, 81–100.
- **Gráfica «Actividad · últimos 14 días»** (líneas): corridas `ok` vs `error` por día, desde la tabla `runs`.
- **Tarjeta explicativa «¿Cómo funciona el Radar?»**: 3 pasos (Operación genera → Leads se trabaja → Panel muestra el resultado).
- Al cargar, también actualiza el badge de leads del menú. **El Panel NO tiene botones de ejecución ni bitácora** (eso vive en Operación y Sistema desde el rediseño v3).

### 4.2. Operación — «El motor del Radar: genera y procesa información, en orden»

- Lista vertical del **pipeline con las 5 etapas** (desde `GET /api/workflows` + último estado desde `GET /api/runs`). Cada tarjeta de etapa muestra:
  - Número de etapa (01–05) y **nombre**: «Radar scrape», «Dedup + score», «Caza señales», «Sync CRM espejo», «Señales LinkedIn».
  - **Descripción** de qué hace (del catálogo `WORKFLOWS` de `server.js`).
  - Chip de **programación**: `0 6 * * 1` (01), `manual / tras 01` (02), `0 7 * * *` (03), `manual (apagado en v1)` (04), `0 8 * * 1` (05).
  - **Badge de última corrida**: «Última: OK · {fecha}» / «En ejecución…» / «Última: error» / «Sin ejecutar aún», con color por estado.
  - Si la última corrida fue error: **el texto del error en rojo**, visible en la tarjeta.
  - Botón **«▶ Ejecutar etapa NN»**: si la etapa previa no está en `ok`, el botón aparece **deshabilitado** con el motivo junto a un 🔒 (mismo texto de la regla R10: nunca/running/error).
- Ejecutar pide **confirmación en modal** («Puede tardar varios minutos (el scraper visita Google Maps)») → `POST /api/run/:stage` → toast con el mensaje del servidor; la vista se recarga (y el polling de 25 s la mantiene viva mientras algo corre).

### 4.3. Leads — «Tus prospectos: contacta, da seguimiento y ciérralos»

- **Toolbar de filtros** (tarjeta): buscador de texto («Buscar por nombre, giro o dirección…»), select de **etapa** (Todas + las 6) y select de **línea** (Todas, Koolkat, Solar, Evaporativa). Filtros en cliente, combinables.
- **Tabla de leads** — columnas exactas:
  1. **Lead**: nombre en negrita + dirección en texto tenue debajo.
  2. **Giro**.
  3. **Score**: barra de progreso (ancho = score %) + número.
  4. **Línea**: punto de color (naranja `#f97316` Koolkat, amarillo `#eab308` Solar, azul `#3b82f6` Evaporativa) + nombre.
  5. **Etapa**: badge (verde si ganado, rojo si perdido, neutro en otro caso).
  6. Chevron `›` (la fila es clicable).
  - Orden: el de la API (`score DESC`). La tabla se viene completa (sin paginación) de `GET /api/leads`.
  - **Estado vacío**: si no hay leads → panel «Sin leads aún» con explicación y botón «Ir a Operación»; si hay leads pero el filtro no deja ninguno → fila «Sin resultados para este filtro.».
- **Clic en una fila → drawer de detalle del lead** (panel lateral derecho, se cierra con ✕, clic en el overlay o Escape). Contenido del drawer:
  - Encabezado: nombre, badge «Score N/100», badge de línea con su punto de color.
  - Sección **«Por qué este lead»**: explicación en lenguaje simple de la línea recomendada (función #97).
  - Sección **«Datos»** (lista clave-valor): Giro, Dirección, **Temperatura zona** (`temp_zona` °C), **Empleados**, **Sector**.
  - Sección **«Cómo contactarlo»** (filas con icono y botón de acción):
    - *Teléfono*: si hay (normalizado, #95) → botones **«Llamar»** (`tel:`) y **«WhatsApp»** (`wa.me`, primario); si no hay → aviso «Sin teléfono registrado — búscalo en su sitio web o LinkedIn».
    - *Sitio web*: si hay → **«Abrir sitio»**; si no → «Sin sitio registrado».
    - *LinkedIn*: siempre → **«Buscar en LinkedIn»** (abre `linkedin.com/search/results/companies/?keywords={nombre}`).
    - *Ubicación*: → **«Ver mapa»** (abre Google Maps con `lat,lng` si existen, o con dirección/nombre).
  - Sección **«Etapa»**: **stepper de 6 píldoras clicables** (Nuevo, Contactado, Reunión, Propuesta, Ganado, Perdido) — las anteriores a la actual se marcan «hechas», «Perdido» en estilo negativo; clic → `PATCH /api/leads/:id {etapa}` → toast + la tabla y el drawer se refrescan.
  - Sección **«Notas»**: textarea con las notas del lead + botón **«Guardar notas»** (`PATCH {notas}`).
  - Sección **«Señales»**: texto explicativo (+25) + botón **«＋ Registrar señal»** → modal con campos: Empresa (precargada), Giro (precargado), **Tipo** (select: hallazgo, ampliación, cambio de gerente, licitación, nota de prensa, otro), Evidencia (textarea, requerida) → `POST /api/signals` → toast «Señal registrada… la etapa 03 la procesa (+25)».

### 4.4. Mapa — «Tus prospectos en el territorio»

- Mapa Leaflet (tiles OpenStreetMap, centro inicial: México `[23.5, -102]`, zoom 5), con control de capas propio de Leaflet para encender/apagar los grupos **Leads** y **Temperatura**.
- **Barra de filtros**: select de **línea** (Todas/Koolkat/Solar/Evaporativa), select de **etapa** (Todas + las 6), checkbox **«Capa de temperatura»** (marcado por default).
- **Marcadores**: un `circleMarker` por lead **con lat/lng** (los leads sin coordenadas no se pintan, pero sí están en la tabla de Leads), coloreado por línea recomendada.
- **Capa de temperatura**: por cada lead con `temp_zona`, un círculo rojo semitransparente con radio según la regla R13 y tooltip «N °C».
- **Leyenda** fija: punto naranja = Koolkat, amarillo = Solar, azul = Evaporativa.
- **Popup de cada marcador**: nombre en negrita, `giro · score N`, «Etapa · Línea» y dos mini-acciones:
  - **«Ver detalle»** → abre el drawer del lead (#4.3) sin salir del mapa.
  - **«Clima»** → consulta `GET /api/weather?lat&lng` y muestra en el popup «Ahora: N °C» (con marca «(caché)» si viene del caché de 6 h).

### 4.5. Sistema — «Salud, conexiones y ajustes. Si algo falla, se ve aquí»

Cinco tarjetas apiladas:

1. **Diagnóstico** (con botón «Revisar de nuevo»): semáforo de 5 filas con punto de color (verde `ok` / ámbar `warn` / rojo `error`) y mensaje del servidor:
   - *Base de datos* (`checks.postgres`), *Proveedores* (`checks.providers`), *Cobertura de líneas* (`checks.cobertura_lineas` — si no está ok, la fila trae botón **«Ir a Operación»**), *n8n (automatización)*, *Scraper* (muestra el backend activo: local/apify).
   - Al cargarse también actualiza el dot de conexión del header y el dot de advertencia del menú.
2. **Proveedores**: explicación («cada capacidad corre en local $0; cambia a nube con capa gratuita») + **tabla** con columnas:
   - **Capacidad**: etiqueta + descripción de la opción nube; en la fila de **LinkedIn**, además, un input «org_id numérico de tu página» con botón **«Guardar»** (`PATCH providers/linkedin {config:{org_id}}`).
   - **Modo**: control segmentado con un botón por modo válido (local/cloud/disabled según capacidad); clic → `PATCH {mode, provider}` eligiendo automáticamente el backend coherente (al pasar a cloud elige el backend nube; a local, `local`); pasar a **cloud pide confirmación** («asegúrate de tener la API key en el .env»).
   - **Backend**: select si hay más de un backend (ej. crm: local/hubspot/twenty), o texto fijo si solo hay uno; cambiar → `PATCH {provider}`.
3. **LinkedIn · página de empresa** (desde `GET /api/linkedin/status`) — tres estados:
   - *Sin `LINKEDIN_CLIENT_ID`*: error en rojo con instrucciones (crear app en developer.linkedin.com y reconstruir el dashboard).
   - *No conectado*: explicación + **nota honesta** («la API no permite buscar prospectos; aquí se monitorean señales de tu propia página») + botón **«Conectar LinkedIn»** (abre `/api/linkedin/auth` en pestaña nueva) y botón «Ya autoricé, actualizar».
   - *Conectado*: badge «Conectado» + badge «Token expirado — reconecta» si aplica (o «Token vigente»), **stats**: Seguidores / Posts / Engagement (del día más reciente), lista de **señales cálidas pendientes** (título, detalle, fecha; si no hay: «Sin señales cálidas pendientes. La etapa 05 las genera cada lunes»), y botón **«Desconectar»** (con modal de confirmación → `POST /api/linkedin/disconnect`).
4. **Bitácora de ejecuciones**: tabla de las **últimas 30** corridas locales con columnas **# (id), Etapa, Estado (badge), Inicio, Fin, Detalle**; las filas en `error` se pintan en rojo y su detalle en texto de error; el detalle se «desempaca» (si es JSON muestra su `error`/`mensaje`/`nota`). Estado vacío: «Sin ejecuciones aún. Ve a Operación y corre la etapa 01». Si falta `N8N_API_KEY`, una fila final lo explica («solo afecta la lectura»).
5. **Configuración técnica** (desde `GET /api/config`): lista clave-valor con Versión, Zona horaria, n8n (URL + si su API key está configurada), **Webhooks** (chip ✓/✗ por `radar-01…05`) y **Keys de nube** (chip ✓/✗ por apify/apollo/hubspot/linkedin) con la nota «Solo se muestra si existen, nunca los valores. Van en el .env».

---

## 5. Credenciales y piezas externas referenciadas (para reproducir el sistema)

| Pieza | Detalle exacto |
|---|---|
| Credencial n8n «Postgres Radar» | Nombre exacto (los 5 workflows la referencian): host `postgres`, puerto 5432, BD `radar`, usuario `postgres`, password del `.env` |
| Credencial n8n «Apollo API» | Header Auth: header `x-api-key` con la key de Apollo |
| Credencial n8n «HubSpot» | Header Auth: Name=`Authorization`, Value=`Bearer <Private App token>`; scope `crm.objects.companies.write` |
| App de LinkedIn | developer.linkedin.com; Products: *Share on LinkedIn* + *Sign In with LinkedIn using OpenID Connect* + solicitar *Community Management API*; Redirect URL: `http://localhost:3000/api/linkedin/callback` |
| Servicios | Dashboard http://localhost:3000 · n8n http://localhost:5678 · Scraper http://localhost:5000/health |
| Dependencias dashboard | `express ^4.19.2`, `pg ^8.12.0` (Node 20) — `dashboard/package.json` |
| Dependencias scraper | `flask 3.0.3`, `psycopg[binary] 3.2.3`, `requests 2.32.3` (imagen Playwright Python v1.49.0-jammy) |
| CDN del frontend | Leaflet 1.9.4, ECharts 5.5.1 (si no hay internet, las gráficas muestran aviso y el mapa no carga) |
