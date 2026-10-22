# GEIS — GeoEnterprise Intelligence System

Plataforma open source de geomarketing para México: unifica DENUE, el Censo de Población y Vivienda y el Marco Geoestadístico del INEGI sobre PostgreSQL + PostGIS para evaluar ubicaciones comerciales, generar leads B2B con scoring espacial (ISM, Huff, TAM, IDT) y producir reportes de viabilidad con veredicto.
Este repositorio contiene la **infraestructura local** (Docker Compose) y la documentación; el backend (FastAPI) vive en `backend/` y el frontend (React) en `frontend/`, aportados por sus respectivos workers.

## Requisitos

- Docker Engine 24+ con el plugin **Docker Compose v2** (`docker compose version`)
- ~4 GB de RAM libres recomendados

## Quickstart

1. Copia la plantilla de variables de entorno:
   ```bash
   cp .env.example .env
   ```
2. Levanta los servicios base en segundo plano (construye las imágenes la
   primera vez):
   ```bash
   docker compose up --build -d
   # (n8n y el scraper usan el perfil `automation`; ver `make n8n`)
   ```
3. Aplica las migraciones de la base de datos (crean las tablas):
   ```bash
   make migrate
   ```
4. Carga los datos de muestra:
   ```bash
   make seed
   ```
5. Abre en tu navegador:
   - Web: <http://localhost:3000>
   - Documentación del API: <http://localhost:8000/docs>

## Primer arranque: configura tu empresa

Antes de analizar nada, el sistema necesita saber a qué giro se dedica tu empresa. Es **una sola configuración** y de ella dependen todos los cálculos (scoring, TAM, líneas de producto, reportes).

1. Abre <http://localhost:3000> → verás el banner **"Aún no configuras tu empresa → Configurar ahora"**.
2. El wizard tiene 4 pasos:
   - **Giro**: elige entre Climatización, Gimnasios, Cafeterías/Restaurantes, Talleres mecánicos o Personalizado.
   - **Perfil**: completa el documento `PERFIL-EMPRESA.md` en el editor. Puedes cargarlo a mano, usar la plantilla, o pulsar **"Llenar con IA"** (pega la URL de tu empresa o sube un .md/.txt y la IA lo rellena marcando `[PENDIENTE]` lo que no encuentre). La checklist lateral te dice en vivo qué campos críticos faltan.
   - **API keys IA** (opcional): configura hasta 5 proveedores (OpenAI, Anthropic, Gemini, Groq, DeepSeek) para el asistente interno. El botón genera las líneas exactas para pegar en tu `.env` y reiniciar la API.
   - **Resumen**: revisa la configuración vertical derivada automáticamente (SCIAN objetivo, pesos de scoring, tickets TAM, canales) y pulsa **"Guardar y activar"**.
3. Desde ese momento: el scoring usa tus pesos, los reportes llevan el nombre de tu empresa, el asistente (página **Asistente IA**) responde sobre tu negocio y el sistema **aprende solo** (cada lead ganado y cada reporte alimentan el conocimiento local).

Detalle técnico: `docs/MODULO-CONFIGURACION-IA.md`. Plantilla: `docs/PERFIL-EMPRESA.md`.

## URLs

| Qué | URL |
|---|---|
| Aplicación web | <http://localhost:3000> |
| API (docs interactivos) | <http://localhost:8000/docs> |
| API (OpenAPI JSON) | <http://localhost:8000/openapi.json> |
| n8n (orquestador, perfil `automation`) | <http://localhost:5678> |
| Scraper (API interna del provider) | <http://localhost:5000/health> |

## Servicios y puertos

| Servicio | Imagen / build | Host → contenedor | Descripción |
|---|---|---|---|
| `db` | `postgis/postgis:16-3.5` | 5432 → 5432 | PostgreSQL 16 + PostGIS 3.5; esquemas `prod`, `stg`, `quarantine` |
| `redis` | `redis:7-alpine` | — → 6379 | Caché de API y rate limiting |
| `api` | `./backend` (`python:3.11-slim`) | 8000 → 8000 | FastAPI (`uvicorn app.main:app`) |
| `web` | `./frontend` (`node:20-alpine` → `nginx:alpine`) | 3000 → 80 | SPA React servida por Nginx |
| `n8n` | `n8nio/n8n` (perfil `automation`) | 5678 → 5678 | Orquestador de los 5 workflows del módulo Radar |
| `scraper` | `./scraper` (`python:3.11-slim` + Playwright) | 5000 → 5000 | Scrapeo de Google Maps → staging crudo (`/scrape`, `/health`) |
| `cloudflared` | `cloudflare/cloudflared` (perfil `tunnel`) | — | Túnel rápido público hacia el frontend |

Red interna común: `geis-net`. Volúmenes persistentes: `pgdata` (datos de
Postgres) y `n8n_data` (credenciales y ejecuciones de n8n).
`web` depende de `api` y `api` depende de `db` y `redis`, todos con `condition: service_healthy`.
`n8n` y `scraper` solo arrancan con el perfil `automation`; `cloudflared`, con `tunnel`.

## Ecosistema GEIS × Radar

**Tesis:** GEIS es la **capa de inteligencia** (¿dónde están las oportunidades? — datos oficiales, modelos espaciales, veredictos) y el **módulo Radar** es la **capa de ejecución** (¿cómo las capturo? — scrapeo, scoring conductual, señales, pipeline comercial, CRM). No compiten: se ensamblan sobre la misma infraestructura (PostGIS + FastAPI + React/shadcn + Docker Compose local-first).

### Qué es el módulo Radar

Adaptación de Biokool Radar v3 sobre GEIS, sin duplicar nada: una sola tabla de leads (`prod.leads` con `source` denue/gmaps/manual/linkedin), un solo score (espacial + conductual), un solo mapa, un solo dashboard, una sola API. Aporta lo que GEIS no tenía:

- **Scrapeo de Google Maps** → leads crudos en `stg.leads_raw`.
- **Scoring conductual**: +temperatura Open-Meteo (> 30 °C), +señales manuales/cálidas, engagement de LinkedIn; línea recomendada por mes (`koolkat`/`solar`/`evaporativa`).
- **Pipeline comercial** de 6 etapas (nuevo → contactado → reunión → propuesta → ganado/perdido) con acciones de contacto (llamar, WhatsApp, sitio, LinkedIn) y notas del SDR.
- **Bitácora de corridas** (`prod.runs`) con **bloqueo por orden**: el backend rechaza un paso si el anterior no terminó OK (la UI muestra el motivo).
- **Capa de providers anti-cautiverio**: cada capacidad (scraper, enrichment, crm, email, weather, linkedin, geocoding, routing) conmuta entre `local`, `cloud` o `disabled` desde la página **Sistema**.
- **Integración LinkedIn**: estadísticas de la página de empresa → picos de engagement → señales cálidas (+score).

### Runbook de pipelines (página Operación)

Orden de ejecución del módulo Radar: **01 → 02 → 03 → 04 → 05**. Los ETL de GEIS (`etl-denue`, `etl-censo`) también se lanzan y registran desde la misma página.

```bash
# 1. Levanta el orquestador (perfil opcional: n8n suma ~400 MB de RAM)
make n8n

# 2. Abre Operación en la web y pulsa ▶ en cada paso, en orden:
#    radar-01 (scrapeo) → radar-02 (deduplicado + score) → radar-03 (señales)
#    → radar-04 (CRM) → radar-05 (LinkedIn)

# 3. Si un paso se bloquea, la API responde 409 y la UI muestra el motivo
#    (el paso anterior no terminó OK). Revisa la bitácora y reintenta.

# 4. Logs del scraper durante el paso 01
make scraper-logs
```

Equivalente por API: `POST /api/v1/pipelines/run/{stage}` con `{stage}` en `radar-01..05`, `etl-denue`, `etl-censo`; bitácora en `GET /api/v1/pipelines/runs`.

### Tabla de providers

| Provider | Tipo | Modo `local` | Modo `cloud` | Modo `disabled` |
|---|---|---|---|---|
| `scraper` | scrape | Playwright en `:5000` | Apify | Se salta el paso 01 |
| `enrichment` | enrich | Sin enriquecer (datos crudos) | Apollo (~900–1,200 créd/año) | Se salta la rama Apollo del paso 02 |
| `crm` | crm | Fin del paso 04 (los leads quedan en Postgres) | HubSpot (1,000 contactos) / Twenty | No se espeja |
| `email` | email | Apagado (fase 1) | Apagado (fase 1) | Apagado — nunca el dominio corporativo |
| `weather` | weather | Open-Meteo (gratis, sin clave, caché 6h) | — | Sin componente de temperatura en el score |
| `linkedin` | signals | Sin lectura | App LinkedIn (OAuth, permisos Community Management) | Paso 05 sin datos |
| `geocoding` | geocode | Geocodificador local | Proveedor comercial | Sin geocodificación |
| `routing` | route | Cálculo local | Proveedor comercial | Sin rutas |

Regla de oro: los datos aterrizan primero en Postgres; la nube es espejo. Si la nube falla, el pipeline usa el modo local o salta la rama. Se conmutan en **Sistema → Providers** (`PUT /api/v1/providers/{name}` con `{"mode": "local|cloud|disabled"}`).

## Comandos del Makefile

| Comando | Qué hace |
|---|---|
| `make up` | `docker compose up --build -d` — levanta los servicios base en segundo plano |
| `make down` | Detiene y elimina contenedores (conserva los datos) |
| `make build` | Construye las imágenes sin levantar los servicios |
| `make logs` | Muestra los logs de todos los servicios en vivo |
| `make migrate` | `docker compose exec api alembic upgrade head` — aplica las migraciones (crea las tablas) |
| `make seed` | `docker compose exec api python -m app.seed` — carga datos de muestra |
| `make test` | `docker compose exec api pytest -q` — suite de pruebas del backend |
| `make psql` | Abre `psql` contra la base del proyecto |
| `make clean` | Detiene todo y **borra** volúmenes (datos) e imágenes locales |
| `make help` | Muestra la ayuda con todos los comandos |
| `make n8n` | `docker compose --profile automation up -d n8n` — levanta el orquestador del módulo Radar |
| `make scraper-logs` | Logs en vivo del scraper durante el pipeline radar-01 |

## Estructura del repo

```
geis/
├── docker-compose.yml      # Orquestación: db, redis, api, web (+ n8n, scraper, cloudflared en perfiles)
├── .env.example            # Plantilla de variables (copiar a .env)
├── Makefile                # Atajos: up, down, build, logs, migrate, seed, test, psql, clean, help, n8n, scraper-logs
├── README.md               # Este archivo
├── .gitignore
├── db/
│   └── init.sql            # Extensiones (postgis, pg_trgm, uuid-ossp) y
│                           # esquemas prod/stg/quarantine (corre una sola vez)
├── n8n/                    # (módulo Radar) 5 workflows: radar-01..05 (triple trigger)
├── scraper/                # (módulo Radar) Playwright → /scrape, /health (:5000)
├── signals/                # (módulo Radar) input.json con señales manuales del SDR
├── backend/                # (worker backend)
│   ├── Dockerfile          # Imagen python:3.11-slim + uvicorn
│   ├── requirements.txt
│   ├── app/                # Código FastAPI  ← no tocar (otro worker)
│   └── alembic/            # Migraciones (las TABLAS las crea Alembic)
└── frontend/               # (worker frontend)
    ├── Dockerfile          # Multietapa: node:20-alpine → nginx:alpine
    ├── nginx.conf          # SPA con fallback a index.html; /api/ → api:8000
    └── src/                # Código React  ← no tocar (otro worker)
```

## Notas

- **Datos de muestra deterministas:** `make seed` carga siempre los mismos datos a partir de una semilla fija; ideal para demos y pruebas reproducibles.
- **Sin secretos en código:** las credenciales viven en `.env` (que **no** se commitea — ver `.gitignore`); `.env.example` solo trae valores de desarrollo. Cambia `SECRET_KEY`, `POSTGRES_PASSWORD` y `DENUE_API_TOKEN` antes de cualquier despliegue expuesto.
- **Base de datos:** la primera vez que se crea el volumen `pgdata`, el contenedor `db` ejecuta `db/init.sql` (extensiones + esquemas). Las tablas las crea **Alembic**: corre `make migrate` (equivalente a `docker compose exec api alembic upgrade head`) antes del primer `make seed`; el `init.sql` no se vuelve a ejecutar salvo que borres el volumen (`make clean`).
- **Desarrollo:** `./backend` se monta en vivo sobre `/code`, así los cambios del API se reflejan sin reconstruir la imagen (reinicia con `docker compose restart api` si hace falta).
- **Mismo origen:** el frontend consume el API por rutas relativas `/api/…`; Nginx las proxya a `api:8000`, por lo que no se necesita CORS en local. Si el frontend se despliega separado, define `VITE_API_URL` en el build.
- **Puertos ocupados:** si el 5432, 8000 o 3000 ya están en uso en tu máquina, edítalos en `docker-compose.yml` (lado izquierdo del mapeo).
- **Fase 2 (no implementado en el backend):** la UI ya muestra con tooltips honestos lo que aún no existe — `GET /api/v1/reports/{id}/pdf` (descarga PDF del reporte), `POST /api/v1/leads/sync` (sincronización al CRM) y `DELETE /api/v1/investigations/{id}` (re-ejecutar = crear una nueva investigación vía `POST /api/v1/investigations`). La exportación de leads a CSV sí existe: `POST /api/v1/leads/export?formato=csv` (tope 5,000 filas; `formato=excel` responde 501).
- **Portada del ecosistema:** al abrir <http://localhost:3000> verás la página **Inicio**: un dashboard de KPIs generales del módulo Radar (leads, enriquecidos, en CRM, embudo por etapa, línea recomendada, última operación del pipeline), el estado del sistema, el territorio activo y los 3 flujos principales (analizar territorio, captar y contactar, gobernar el sistema); las insignias "Estimado" marcan los valores calculados.
