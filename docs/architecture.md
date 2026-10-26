# GEIS — Arquitectura

## Vista general

```mermaid
flowchart LR
    subgraph Host["Host Windows · Docker Compose"]
        subgraph PerfilBase["Perfil base"]
            DB[("db · PostGIS 16-3.5\nesquemas prod/stg/quarantine")]
            RD[("redis:7-alpine\ncaché + rate limit")]
            API["api · FastAPI :8000\n/api/v1/* · Alembic · Pydantic"]
            WEB["web · Nginx :3000\nSPA React 18 (Vite+TS)"]
        end
        subgraph PerfilAutomation["Perfil automation"]
            N8N["n8n :5678\nworkflows radar-01..05"]
            SCR["scraper :5000\nPlaywright + Chromium"]
        end
        CLOUD["cloudflared (perfil tunnel)"]
    end

    N8N -- "HTTP interno" --> API
    N8N -- "SQL directo (credencial Postgres GEIS)" --> DB
    N8N -- "HTTP /scrape" --> SCR
    N8N -- "APIs nube" --> APO[Apollo.io]
    N8N -- "APIs nube" --> HS[HubSpot]
    N8N -- "APIs nube" --> LI[LinkedIn]
    N8N -- "señales manuales" --> SIG["signals/input.json (volumen)"]
    SCR --> OM[Open-Meteo · Google Maps]
    API --> RD
    API --> DB
    API -- "geocoding / reverse" --> NOM[Nominatim · OSM]
    API -- "isócronas" --> VAL[Valhalla · OSM]
    API -- "vialidades" --> OVP[Overpass · OSM]
    WEB -- "/api/ → proxy" --> API
    CLOUD --> WEB
```

- **Red interna común**: `geis-net`. **Volúmenes persistentes**: `pgdata` (Postgres), `n8n_data` (credenciales/ejecuciones n8n), `signals/` (bind mount, entrada del paso 03).
- `web` depende de `api` (healthy); `api` de `db` y `redis` (healthy). `n8n`/`scraper` solo arrancan con `--profile automation`; `cloudflared` con `tunnel`.
- **Mismo origen**: el frontend consume rutas relativas `/api/…`; Nginx las proxya a `api:8000` (sin CORS en local).
- **Dos secciones de producto** (ADR-008): 📍 **Ubicaciones** (análisis tipo Sabueso: `Analizar → Reporte → Mapa → Comparador → Historial → Aprende`) y 🎯 **Radar** (`Panel Radar → Operación → Leads → Mapa Radar → KPIs → Geofencing → Exportación`). Inicio y Sistema son comunes. Una sola SPA, una sola API.

## Capas

### 1. Capa de datos (PostgreSQL + PostGIS)

- Imagen `postgis/postgis:16-3.5` (upgrade desde 15-3.4; ver [ADR-001](decisions/ADR-001-postgis-16-35.md)).
- Extensiones (`db/init.sql`, corre una sola vez al crear el volumen): `postgis`, `pg_trgm`, `uuid-ossp`.
- Esquemas separados por ciclo de vida:
  - `prod.*` — verdad operativa: `leads` (con geografía derivada: `entidad/municipio/colonia/cp/scian`), `runs`, `providers`, `warm_signals`, `linkedin_stats`, `denue_establishments`, `user_investigations` (con `es_principal`), `report_shares`, territorios/reportes/propuestas (GEIS).
  - `stg.*` — landing crudo: `leads_raw` (salida del scrapeo, con flag `procesado`).
  - `quarantine.*` — registros rechazados por validación.
- Las **tablas** las crea **Alembic** (`make migrate`), no `init.sql`. Cadena vigente: `0001 → … → 0004 → 0005 (geo leads) → 0006 (shares + es_principal)`.

### 2. Capa de API (FastAPI)

- Entrada `backend/app/main.py`, routers en `backend/app/api/v1/` (16 routers; detalle en [api/rest.md](api/rest.md)).
- Patrones clave:
  - **Paginación por cursor** en `/leads` y `/leads/curados`: `limit` (máx. **100**, `FastAPI Query(le=100)`) + `cursor`/`next_cursor`. Para el total exacto existe **`GET /leads/count`** (filtros etapa/línea/source/geo); ya no hace falta iterar el cursor para contar.
  - **Filtros geográficos** `entidad/municipio/colonia/cp/scian` en `/leads`, `/leads/curados` y `/leads/count`; valores con cascada en `GET /catalogs/geo-filters`. Los campos se derivan con `POST /leads/enrich-geo` (migración 0005).
  - **Geocoding real** (`POST /territories/geocode`): coordenadas, links de Maps (largos/cortos) o dirección con Nominatim/OSM; **422 si no resuelve** (nunca un punto por defecto).
  - **Gating por orden** en `POST /pipelines/run/{stage}`: `409` si el paso anterior no terminó OK (el pipeline se lee de `prod.runs`).
  - **Capa de providers**: cada capacidad (`scraper`, `enrichment`, `crm`, `email`, `weather`, `linkedin`, `geocoding`, `routing`) tiene fila en `prod.providers` con `mode` local/cloud/disabled; el backend resuelve la ruta según modo.
  - **Modelo estricto Pydantic**: `RunOut` exige `detalle` como `dict` — arrays o `NULL` en `prod.runs.detalle` provocan `500` (ver [ADR-005](decisions/ADR-005-gobernanza-prod-runs-detalle.md)).
- Montaje en vivo: `./backend` → `/code` (cambios sin rebuild; `docker compose restart api`).

#### Reporte de ubicación (Sección 1)

```
POST /reports
  → compute_location_analysis (ISM, Huff, TAM, anillos)
  → build_report_context (app/reports/context.py)
       ├── INEGI: población/segmentos/hogares/PEA/NSE (AGEB por radio)
       ├── DENUE: entorno de 9 categorías, competencia con distancia, atractores, anclas
       ├── Valhalla: isócronas 5/10/15 min (si falla → radios declarados)
       ├── Overpass: vialidades principales (si falla → [] honesto)
       └── fichas sectoriales + editorial cacheado (knowledge_facts)
  → build_location_report (24 claves de payload)
  → persistencia en prod.reports
GET /reports/{id}                      → JSON completo
POST /reports/{id}/share               → token en prod.report_shares
GET /reports/shared/{token}            → público solo lectura (404 si expiró/revocado)
DELETE /reports/{id}/share/{token}     → revoca (204)
```

El efecto ancla (`analytics/anclas.py`) multiplica la atractividad en Huff por
`1 + Σ w_a`; los proxies de movilidad (`analytics/movilidad.py`) siempre salen
con `estimado: true` y método declarado.

### 3. Capa de orquestación (n8n)

- Versión **2.35.7**, credenciales cifradas con `N8N_ENCRYPTION_KEY` (64 hex) del `.env`.
- 5 workflows en `n8n/workflows/*.json`, importados por ID (Nanoid top-level) vía `n8n import:workflow --separate` (upsert); 3 credenciales inyectadas programáticamente (`n8n import:credentials`): **Postgres GEIS** (`ssl:"disable"`), **Apollo API**, **HubSpot**.
- **Triple trigger** por workflow: webhook desde la API, manual (UI) y CLI (`n8n execute`).
- Acceso a archivos restringido a `/signals` (`N8N_RESTRICT_FILE_ACCESS_TO=/signals`).
- Ver [ADR-002](decisions/ADR-002-endurecimiento-n8n.md) y [ADR-003](decisions/ADR-003-code-nodes-n8n.md).

#### Pipeline Radar (orden 01 → 05)

| Stage | Workflow | Qué hace | Salida |
|---|---|---|---|
| `radar-01` | `01-radar-scrape.json` | Scrapear Google Maps (vía scraper o Apify cloud) | `stg.leads_raw` |
| `radar-02` | `02-dedup-score.json` | Dedup contra `prod.leads`, scoring conductual (+Open-Meteo), línea recomendada, enriquecimiento Apollo (rama cloud), geocodificación → `temp_zona` | `prod.leads` |
| `radar-03` | `03-signal-catcher.json` | Lee `signals/input.json` (nodo Parsear JSON), consolida señales cálidas | `prod.warm_signals`, `prod.leads` |
| `radar-04` | `04-crm-sync.json` | Espeja leads a HubSpot con propiedades custom `biokool_etapa/score/linea` | HubSpot Companies |
| `radar-05` | `05-linkedin-signals.json` | Estadísticas de página LinkedIn (Biokool, org `107784991`) → picos de engagement | `prod.linkedin_stats`, `prod.warm_signals` |

Flujo detallado del paso 03 (post-fix):

```
Leer signals/input.json (Read Binary File)
  → Parsear JSON (extractFromFile · fromJson · binaryProperty "data")   ← evita BOM
  → Parsear señales (Code · runOnceForAllItems · lee $input.first().json.data)
  → Consolidar / Armar warm
  → API backend /signals + /leads
```

### 4. Capa de presentación (React SPA)

- Stack: React 18.3, react-router-dom 6, Vite 5.4, TypeScript 5.5, Tailwind 3.4, Radix UI (shadcn), TanStack Table 8, **ECharts 5.5**, **Leaflet 1.9 + react-leaflet 4.2 + geoman 2.17**, zustand 4, sonner.
- **Shell:** `AppLayout` + `Sidebar` con selector de sección persistente (`localStorage: geis:seccion`). Rutas sin chrome: `/reporte/:id/imprimir` (imprimible) y `/r/:token` (compartido público).
- **Sección 1 · Ubicaciones:** `Analizar` (giro + dirección/link → pin arrastrable → reporte), `Reporte` (mapas Leaflet de anillos/atractores/isócronas, dona ECharts, acordeones, calculadoras, WhatsApp/PDF/invitado), `Mapa`, `Comparador` (2–6, ganadora persistente), `Historial`, `Aprende`.
- **Sección 2 · Radar:** `PanelRadar` (4 alertas/KPIs/gráficas), `Operacion` (5 etapas + gating, providers, LinkedIn, clima, enrich-geo), `Leads` (filtros geo, drawer «Cómo contactarlo», `whyLinea`), `Mapa` con `?modo=radar`, `Kpis`, `Geofencing`, `Exportacion`.
- **Comunes:** `Inicio` (centro de mando), `Sistema` (salud/providers/workflows), `Configuracion`, `Asistente`.
- Cliente API central: `frontend/src/lib/api.ts` + `apiGeo.ts` (helpers geo, `normPhone`, `normWeb`, `whyLinea`); interfaces TS espejo de los modelos Pydantic.
- Mapa: herramientas de dibujo geoman y `ZoomControl` en `topright` (la leyenda "Capas" vive en `topleft`, `z-[500]` — por eso se movieron los controles).

### 5. Capa de scraping (scraper)

- Python 3.11-slim-**bookworm** + Playwright 1.49.0 + Chromium (`playwright install --with-deps chromium` en build; imagen ~2.1 GB).
- Endpoints: `POST /scrape` (Google Maps → leads crudos), `GET /health`.
- Modo `cloud` alternativo: Apify (plan FREE, token validado).

## Flujo de datos end-to-end (camino feliz)

```mermaid
sequenceDiagram
    participant UI as Operación (web)
    participant API as FastAPI
    participant N8 as n8n
    participant DB as PostGIS
    participant EXT as Nube (Apollo/HubSpot/LinkedIn/Open-Meteo)

    UI->>API: POST /pipelines/run/radar-01
    API->>API: gating (¿run previo OK?)
    API->>N8: trigger webhook
    N8->>EXT: scrape / enriquecer / sincronizar
    N8->>DB: upsert stg.leads_raw / prod.leads
    N8-->>API: resultado
    API->>DB: prod.runs (status ok, detalle dict)
    UI->>API: GET /pipelines/runs (bitácora)
```

## Áreas críticas y riesgos

| Riesgo | Mitigación |
|---|---|
| `N8N_ENCRYPTION_KEY` cambia → credenciales ilegibles + crash loop | Generarla una vez, jamás rotarla sin re-importar credenciales |
| `prod.runs.detalle` como array/NULL → 500 en `/pipelines/runs` | ADR-005: siempre `dict` (JSONB objeto) |
| BOM en JSON leídos por n8n (`Unexpected token '~'`) | Escribir UTF-8 **sin BOM**; nodo `Parsear JSON` intermedio |
| Code nodes devolviendo arrays crudos → "A 'json' property isn't an object" | ADR-003: return `{ json: {...} }` |
| `limit > 100` en `/leads*` → 422 | ADR-004: el frontend pide ≤100 y pagina por cursor; para contar usa `/leads/count` |
| Browser cache con bundle viejo → 404 `/api/runs/activos` | Hard refresh; no es código actual |
| LinkedIn token expira | `expires_at` guardado en provider; re-OAuth manual |
| Nominatim no resuelve una dirección | 422 con mensaje accionable; nunca se devuelve un punto por defecto |
| Overpass a capacidad (502) o Valhalla caído | El reporte sale sin vialidades o con `alcance_tipo="radios"`; el método se declara, no se inventan datos |
| Links de invitado con datos sensibles | Token opaco, expiración ≤365 días y revocación inmediata (`DELETE …/share/{token}`) |

## Antipatrones a evitar

- No escribir en `backend/app` ni `frontend/src` **sin autorización explícita** del owner (regla `AGENTS.md`; ver [conventions.md](conventions.md) y excepciones ADR-004 y ADR-008).
- No usar booleanos en `ssl` de credenciales Postgres de n8n (Postgres node v2.6 exige string `"disable"`).
- No inventar datos cuando una fuente externa falla: vacío/`null` + método declarado (geocoding → 422; movilidad → `estimado: true`; isócronas → radios).
- No commitear `.env`, backups SQL ni `signals/input.json`.
