# ECOSISTEMA GEIS × BIOKOOL RADAR — Blueprint de fusión v1.0

> **Tesis de la fusión:** GEIS es la **capa de inteligencia** (¿dónde están las oportunidades? — datos oficiales, modelos espaciales, veredictos) y Biokool Radar es la **capa de ejecución** (¿cómo las capturo? — scrapeo, scoring conductual, señales, pipeline comercial, CRM). No compiten: se ensamblan. La infraestructura que se conserva es la de GEIS (PostGIS + FastAPI + React/shadcn + Docker Compose local-first); todas las funciones de Radar se adaptan sobre ella sin duplicar nada.

Fecha: 19 de octubre de 2026 · Estado: **implementado** (migración 0002, routers
`pipelines`/`providers`/`signals`/`proposals`/`geo_weather`/`system`/`integrations/linkedin`,
5 workflows n8n, scraper, `signals/`, páginas Operación y Sistema). Este
documento conserva el diseño original; donde la implementación final difirió del
texto inicial se actualizó el apartado correspondiente.

---

## 1. Inventario funcional de Biokool Radar v3 (revisado del repo)

### 1.1. Servicios (docker-compose, 5 + túnel)

| Servicio | Tecnología | Puerto | Rol |
|---|---|---|---|
| `postgres` | PostgreSQL 16 + pgdata | 5432 | **Fuente de verdad**: leads, runs, providers, proposals, signals |
| `n8n` | n8n self-hosted | 5678 | Orquestador de pipelines (5 workflows, triple trigger) |
| `dashboard` | Node 20 + Express, vanilla JS | 3000 | Monitor/control: Panel, Operación, Leads, Mapa, Sistema |
| `scraper` | Python Flask + Playwright (o Apify) | 5000 | Scrapeo Google Maps → `leads_raw`; `/scrape`, `/health` |
| `signals` | volumen `./signals:/signals:ro` | — | `input.json` con señales manuales del SDR |
| `cloudflared` | quick tunnel | — | Exposición pública del dashboard (opcional, con PIN por email) |

### 1.2. Modelo de datos (db/init.sql + migrate.sql)

| Tabla | Rol | Quién la escribe |
|---|---|---|
| `leads_raw` | staging crudo del scraper (nombre, giro, dirección, lat/lng, teléfono, web, rating, fuente, query, procesado) | 01 scrape |
| `leads` | base curada: score, `linea_recomendada` (koolkat/solar/evaporativa), `etapa` (nuevo/contactado/reunion/propuesta/ganado/perdido), `temp_zona`, notas, `enriquecido_apollo`, `crm_synced_at` | 02 score, 03 señales, dashboard |
| `runs` | bitácora de ejecuciones (stage, estado running/ok/error, detalle JSONB) — **base del bloqueo por orden** | dashboard (running), n8n (ok/error) |
| `providers` | **capa anti-cautiverio**: 8 providers (scraper, enrichment, crm, email, weather, linkedin, geocoding, routing) con modo local/cloud/disabled | dashboard (Sistema → Proveedores) |
| `proposals` | propuestas por lead (título, línea, monto, estado) — fase 2 | dashboard |
| `linkedin_stats` | métricas de la página de empresa (seguidores, posts, engagement por día) | 05 linkedin |
| `warm_signals` | señales cálidas (fuente, título, detalle, empresa_ref, procesada) | 05 linkedin → 03 procesa |

### 1.3. Workflows n8n (triple trigger: Manual + Schedule + Webhook)

| # | Workflow | Disparo | Función |
|---|---|---|---|
| 01 | radar-scrape | Manual, lunes 6am, webhook `radar-01` | Arma búsquedas → scrapea Maps → normaliza → guarda en raw → Run OK |
| 02 | dedup-score | webhook `radar-02` (+ schedule) | Dedup por `UNIQUE(nombre,direccion)` → enriquece temperatura Open-Meteo (**+20 si >30 °C**) → score + línea recomendada → rama Apollo (top-20 con web) |
| 03 | signal-catcher | Manual, diario 7am, webhook `radar-03` | Lee `signals/input.json` + `warm_signals` → upsert **+25 score** con match |
| 04 | crm-sync | webhook `radar-04` | Si CRM=nube: espeja a HubSpot (upsert) o Twenty (stub); si local: fin |
| 05 | linkedin-signals | Manual, lunes 8am, webhook `radar-05` | OAuth LinkedIn → stats de la página → picos de engagement → `warm_signals` |

**Reglas de negocio v1 (código, no configuración):**
- **Línea recomendada por mes:** feb–jun → `koolkat` (temporada de calor); oct–feb + giro(gasolinera/estacionamiento/comercial) → `solar` (invierno, gasolineras al aire libre); resto → `evaporativa`.
- **Temperatura:** Open-Meteo gratis sin key, caché 6h; >30 °C ⇒ +20 score.
- **Señales:** manual (SDR pega en input.json: empresa, evidencia, fecha, giro, tipo) o cálidas (LinkedIn) ⇒ +25 score.
- **Orden:** el dashboard rechaza 02 si 01 no terminó OK (consulta `runs`).

### 1.4. Dashboard (Express, 14 rutas API)

`GET /api/leads`, `GET /api/leads/:id`, `GET /api/runs`, `POST /api/run/:stage` (con bloqueo por orden), `GET /api/providers`, `GET /api/workflows`, `GET /api/config`, `GET /api/weather` (proxy Open-Meteo con caché), `GET /api/health` (semáforo postgres/n8n/scraper/providers), `POST /api/signals`, LinkedIn OAuth (`/api/linkedin/auth|callback|status`, `POST /disconnect`).

**UI v3** (seccionada): Panel (KPIs ejecutivos, funnel ECharts, alertas), Operación (pipeline 01→05 como pasos conectados con ▶, bloqueo con motivo, errores en rojo), Leads (tabla + drawer por caso: bloque "Cómo contactarlo" — Llamar/WhatsApp/Abrir sitio/Buscar en LinkedIn — stepper de etapa clicable, notas editables, "registrar señal", recomendación en lenguaje llano), Mapa (Leaflet + capa de temperatura), Sistema (diagnóstico semáforo, providers, LinkedIn, bitácora).

### 1.5. Capa de proveedores (anti-cautiverio)

Núcleo local $0 siempre; cada capacidad con backend local + opción nube (Apify,
Apollo ~900–1,200 créd/año, HubSpot 1,000 contactos, email apagado fase 2;
`geocoding` y `routing` tienen backend local y están preparados para un
proveedor comercial). Si la nube falla ⇒ modo local o se salta la rama. Los
datos aterrizan primero en Postgres; la nube es espejo.

---

## 2. Inventario funcional de GEIS v1 (recap)

PostGIS+PostGIS (DENUE particionado, AGEB, Marco), FastAPI (/api/v1: territories, analysis, leads, reports, investigations, catalogs, etl), React+shadcn (66 componentes, 8 páginas: Mapa, KPIs, Leads, Reporte, Comparador, Historial, Geofencing, Exportación), modelos ISM/Huff/TAM/IDT/score-B2B, reporte de 13 secciones con veredicto, auditoría DENUE, ETL propio con cron. **Lo que NO tiene:** orquestación de pipelines, scrapeo, señales conductuales, LinkedIn, sincronización CRM real, capa de proveedores conmutables, bitácora de corridas.

---

## 3. Matriz de fusión (decisión por componente)

| Componente | Origen | Decisión | Destino en el ecosistema |
|---|---|---|---|
| PostGIS + DDL espacial (DENUE, AGEB, Marco) | GEIS | **Conservar** | Núcleo de datos (se extiende, §4) |
| FastAPI + routers /api/v1 | GEIS | **Conservar** | API única (absorbe rutas Express, §6) |
| React + shadcn (66 comp.) + 8 páginas | GEIS | **Conservar** | Frontend único (absorbe vistas Radar, §7) |
| Modelos ISM/Huff/TAM/IDT/score espacial | GEIS | **Conservar** | Motor analítico (se extiende con conductual, §5) |
| Reporte 13 secciones + veredicto | GEIS | **Conservar** | Entregable (se le suma "plan de contacto") |
| n8n + 5 workflows | Radar | **Adoptar** | **Orquestador oficial** del ecosistema (nuevo en GEIS) |
| Scraper Playwright/Apify :5000 | Radar | **Adoptar** | `scraper/` = implementación del provider `scraper` (capacidad de scrapeo; local=Playwright, cloud=Apify) |
| `providers` anti-cautiverio | Radar | **Adoptar** | Gobierno de la capa de conectores GEIS (sustituye config estática) |
| `runs` + bloqueo por orden | Radar | **Adoptar** | Bitácora de pipelines (ETL + radar) |
| Scoring conductual (+20 temp, +25 señales) | Radar | **Fusionar** | Componentes del score unificado (§5) |
| Regla línea por mes | Radar | **Adoptar** | `model_params` vertical `biokool` |
| `signals/input.json` + LinkedIn 05 | Radar | **Adoptar** | Módulo de señales cálidas (nuevo en GEIS) |
| `etapa` 6 estados + acciones contactar | Radar | **Adoptar** | Pipeline comercial del lead (GEIS solo tenía `status` de 4) |
| `proposals` | Radar | **Adoptar** | Módulo propuestas (fase 2 GEIS) |
| Open-Meteo + caché 6h | Radar | **Adoptar** | Provider `weather` |
| Dashboard Express + vanilla JS | Radar | **Eliminar** | Funciones portadas a React (no se porta el servidor) |
| `leads_raw` lat/lng sin PostGIS | Radar | **Migrar** | `stg.leads_raw` con `geom Point 4326` |
| cloudflared | Radar | **Adoptar** | Servicio opcional del compose |
| Email frío | Radar (fase 2) | **Conservar como fase 2** | Provider `email` apagado (misma regla: nunca el dominio corporativo) |

**Cero duplicados resultantes:** una sola tabla de leads, un solo score, un solo mapa, un solo dashboard, una sola API.

---

## 4. Modelo de datos unificado (delta sobre el DDL GEIS)

```sql
-- 4.1. Leads unificada: converge investigation_leads (GEIS) + leads (Radar).
--     Un lead puede nacer del DENUE (denue_id), del scrapeo (gmaps) o manual.
CREATE TABLE IF NOT EXISTS prod.leads (
    lead_id            bigserial PRIMARY KEY,
    source             text NOT NULL CHECK (source IN ('denue','gmaps','manual','linkedin')),
    denue_id           text,                       -- NULL si no viene del DENUE
    cve_ent            char(2),
    investigation_id   uuid REFERENCES prod.user_investigations(investigation_id) ON DELETE SET NULL,
    nombre             text NOT NULL,
    giro               text,
    direccion          text DEFAULT '',
    geom               geometry(Point, 4326),      -- upgrade: antes lat/lng sueltos
    telefono           text,
    web                text,
    rating             numeric(3,2),                -- de Google Maps cuando aplique
    empleados_est      smallint,                   -- estrato ordinal si se conoce
    -- scoring unificado (§5)
    score              numeric(5,2) NOT NULL DEFAULT 0,
    score_components   jsonb NOT NULL DEFAULT '{}',
    -- negocio Biokool
    linea_recomendada  text CHECK (linea_recomendada IN ('koolkat','solar','evaporativa')),
    etapa              text NOT NULL DEFAULT 'nuevo'
                       CHECK (etapa IN ('nuevo','contactado','reunion','propuesta','ganado','perdido')),
    temp_zona          numeric(4,1),
    notas              text DEFAULT '',
    enriquecido_apollo boolean NOT NULL DEFAULT false,
    crm_synced_at      timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source, nombre, direccion)             -- dedup Radar, ahora por fuente
);
CREATE INDEX IF NOT EXISTS ix_leads_geom ON prod.leads USING gist (geom);
CREATE INDEX IF NOT EXISTS ix_leads_etapa ON prod.leads (etapa);
CREATE INDEX IF NOT EXISTS ix_leads_score ON prod.leads (score DESC);

-- 4.2. Staging del scraper (antes leads_raw)
CREATE TABLE IF NOT EXISTS stg.leads_raw (
    raw_id     bigserial PRIMARY KEY,
    nombre     text, giro text, direccion text,
    geom       geometry(Point, 4326),
    telefono   text, web text, rating numeric(3,2),
    fuente     text DEFAULT 'google_maps', query text,
    procesado  boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);

-- 4.3. Bitácora de pipelines (runs) — sirve a n8n Y al ETL GEIS
CREATE TABLE IF NOT EXISTS prod.runs (
    run_id     bigserial PRIMARY KEY,
    pipeline   text NOT NULL,   -- 'radar-01'..'radar-05', 'etl-denue', 'etl-censo'
    estado     text NOT NULL CHECK (estado IN ('running','ok','error')),
    detalle    jsonb,
    started_at timestamptz DEFAULT now(),
    finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS ix_runs_pipe ON prod.runs (pipeline, started_at DESC);

-- 4.4. Providers anti-cautiverio (extiende kinds con conectores GEIS)
CREATE TABLE IF NOT EXISTS prod.providers (
    name       text PRIMARY KEY,   -- scraper|enrichment|crm|email|weather|linkedin|geocoding|routing
    kind       text NOT NULL,      -- scrape|enrich|crm|email|weather|signals|geocode|route
    mode       text NOT NULL DEFAULT 'local' CHECK (mode IN ('local','cloud','disabled')),
    provider   text NOT NULL DEFAULT 'local',
    config     jsonb NOT NULL DEFAULT '{}',
    enabled    boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- 4.5. Propuestas, señales cálidas, LinkedIn (adopción directa de Radar)
CREATE TABLE IF NOT EXISTS prod.proposals (
    proposal_id bigserial PRIMARY KEY,
    lead_id     bigint NOT NULL REFERENCES prod.leads(lead_id) ON DELETE CASCADE,
    titulo      text, linea text, monto numeric(12,2),
    estado      text NOT NULL DEFAULT 'borrador', created_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS prod.warm_signals (
    signal_id   bigserial PRIMARY KEY,
    fuente      text NOT NULL DEFAULT 'linkedin',
    titulo      text, detalle text, empresa_ref text,
    procesada   boolean DEFAULT false, created_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS prod.linkedin_stats (
    stat_id serial PRIMARY KEY, org_id text, followers int,
    posts_count int, engagement_total int, stats_date date DEFAULT CURRENT_DATE,
    raw jsonb, created_at timestamptz DEFAULT now(), UNIQUE (org_id, stats_date)
);
-- 4.6. investigation_leads (GEIS) se conserva como vista/legado o se migra a prod.leads
--      con source='denue' e investigation_id poblado. (Migración en alembic 0002.)
```

---

## 5. Motor de scoring unificado

```
Score(0-100) = 100 × Σ w_m·x_m / Σ w_m   (solo componentes disponibles, todos explicables)

Componentes ESPACIALES (GEIS):            peso base
  x_idt      IDT/100 (§3.4)                 0.30
  x_tamano   estrato normalizado            0.12
  x_acceso   accesibilidad logística        0.10
  x_densidad densidad de cuentas (KDE)      0.08
  x_contacto completitud de contacto        0.05
Componentes CONDUCTUALES (Radar):
  x_temp     1 si temp_zona > 30 °C          0.15   (+20 legacy → normalizado)
  x_senal    1 si hay señal manual/cálida    0.15   (+25 legacy → normalizado)
  x_linkedin engagement cálido reciente      0.05
```

- Los pesos legacy (+20/+25) se **normalizan** a la escala 0–100 (ya no son sumas aritméticas que pueden pasar de 100).
- `score_components` guarda cada x_m y w_m ⇒ el drawer del lead muestra el desglose (Radar) con la rigurosidad GEIS.
- Perfiles por vertical en `model_params` (`biokool`: pesos de arriba; `generico`: solo espaciales).

---

## 6. API unificada (mapeo Express → FastAPI)

| Ruta Radar (Express) | Ruta GEIS (FastAPI) | Notas |
|---|---|---|
| `GET /api/leads`, `GET /api/leads/:id` | `GET /api/v1/leads`, `GET /api/v1/leads/{id}` | Extender con `etapa`, `notas`, filtros por línea |
| — | `POST /api/v1/leads/export?formato=csv` | **Nuevo implementado**: exportación CSV real (tope 5,000 filas, orden `denue_id`); `formato=excel` → **501 honesto** (no disponible) |
| `POST /api/run/:stage` | `POST /api/v1/pipelines/run/{stage}` | Mismo bloqueo por orden (lee `prod.runs`) |
| `GET /api/runs` | `GET /api/v1/pipelines/runs` | Bitácora unificada (n8n + ETL) |
| `GET /api/providers` (+PUT) | `GET/PUT /api/v1/providers` | Gobierno de conectores |
| `GET /api/workflows` | `GET /api/v1/pipelines/workflows` | Lee los JSON de `n8n/` |
| `GET /api/weather` | `GET /api/v1/geo/weather` | Proxy Open-Meteo con caché 6h (Redis) |
| `GET /api/health` | `GET /api/v1/system/health` | Semáforo: postgis, n8n, scraper, providers |
| `POST /api/signals` | `POST /api/v1/signals` | Escribe `warm_signals` (fuente manual) |
| `/api/linkedin/*` | `/api/v1/integrations/linkedin/*` | OAuth igual, tokens en vault/.env |
| — | `POST /api/v1/proposals` | Nuevo (fase 2 Radar) |

**Pendientes honestos (Fase 2, ya marcados con tooltips en la UI):**
| — | `GET /api/v1/reports/{id}/pdf` | **No existe** — descarga PDF del reporte es Fase 2 |
| — | `POST /api/v1/leads/sync` | **No existe** — sincronización al CRM es Fase 2 (el paso 04 solo guarda local) |
| — | `DELETE /api/v1/investigations/{id}` | **No existe** — re-ejecutar = crear una nueva investigación vía `POST /api/v1/investigations` |

El **scraper** conserva su API (`:5000/scrape`, `/health`) y GEIS lo gobierna
como el provider `scraper` de `prod.providers` (modo local=Playwright, cloud=Apify).

---

## 7. Frontend: mapa de páginas fusionadas

| Página GEIS | Cambio por la fusión |
|---|---|
| Mapa | + capa de temperatura Open-Meteo; pines coloreados por `linea_recomendada` |
| KPIs (Panel) | + funnel por `etapa`, dona por línea, alertas de providers, KPIs radar (leads nuevos, contactados, reuniones) |
| Leads | + stepper de `etapa` clicable, drawer "Cómo contactarlo" (Llamar/WhatsApp/Sitio/LinkedIn), notas editables, "registrar señal", score desglosado |
| Reporte | + sección 14 "Plan de contacto sugerido" (línea, argumentos por giro, mejor momento por temperatura) — **implementado**: `sugerir_plan_contacto()` y `builder.py` generan las 14 secciones (`giro=None` → "dato no disponible") |
| **Inicio** (nueva, revisión final) | Portada del ecosistema: los 3 flujos principales, estado del sistema, territorio activo |
| **Operación** (nueva) | Pipeline 01→05 + ETL como pasos conectados, ▶ con bloqueo y motivo, bitácora |
| **Sistema** (nueva) | Diagnóstico semáforo, Providers (local/cloud), LinkedIn, bitácora detalle |
| Comparador, Historial, Geofencing | Sin cambios |
| Exportación | Exportación CSV de leads real (`POST /api/v1/leads/export?formato=csv`, tope 5,000 filas, orden `denue_id`); `formato=excel` → 501 honesto; sync CRM y PDF del reporte → **Fase 2** (UI los deshabilita con tooltip) |

Todo con el sistema shadcn existente; dark/light ya contemplado en Radar → se adopta `ThemeToggle`.

---

## 8. n8n como orquestador oficial

- Los 5 workflows se copian a `geis/n8n/workflows/` adaptados: los webhooks llaman a `POST /api/v1/pipelines/run/{stage}` de FastAPI para el bloqueo por orden; la escritura a Postgres usa las tablas `prod.*`.
- El ETL GEIS (denue/censo/marco) se registra como pipelines `etl-*` en `prod.runs` (mismo semáforo).
- Triple trigger se conserva. `N8N_API_KEY` permite al frontend leer ejecuciones.

## 9. Fases de implementación

1. **Fase A — Datos:** migración Alembic 0002 (tablas §4), seed fusionado (40 DENUE + 12 leads radar de ejemplo con etapas y señales).
2. **Fase B — API:** routers `pipelines`, `providers`, `signals`, `integrations/linkedin`, `proposals`; scoring unificado; `leads` extendido.
3. **Fase C — Automatización:** `n8n/` + `scraper/` + `signals/` integrados al compose (servicios n8n, scraper, cloudflared opcional).
4. **Fase D — UI:** páginas Operación y Sistema; extensiones a Mapa/KPIs/Leads/Reporte.
5. **Fase E — Verificación:** tests del scoring, E2E pipeline 01→03 con seed, `docker compose config`, build frontend.

## 10. Riesgos y decisiones abiertas

- **R-01** Playwright es frágil ante cambios de Google ⇒ el provider conmuta a Apify sin tocar pipelines (ya diseñado).
- **R-02** LinkedIn OAuth requiere app y permisos reales de Chino (Community Management API) — no verificable en este entorno.
- **R-03** n8n suma ~400 MB RAM; en el compose local es opcional (`--profile automation`) para máquinas justas.
- **D-01** ¿Migración de `investigation_leads` a `prod.leads` con backfill, o vista de compatibilidad? (Recomendación: backfill en 0002.)
- **D-02** Nombre del ecosistema: se conserva **GEIS** como plataforma; "Radar" pasa a ser el **módulo de ejecución** (`Módulo Radar`).
