# GEIS — Inventario

## Estructura del repositorio (3 niveles)

```
geis/
├── docker-compose.yml       # Servicios: db, redis, api, web (+ n8n, scraper en `automation`; cloudflared en `tunnel`)
├── .env / .env.example      # Secretos / plantilla (solo .env.example se commitea)
├── Makefile                 # up, down, build, logs, migrate, seed, test, psql, clean, n8n, scraper-logs, help
├── README.md
├── backup_pg15_20261019_2059.sql   # Backup pre-upgrade (NO se commitea; .gitignore)
├── db/init.sql              # Extensiones postgis/pg_trgm/uuid-ossp + esquemas (una sola vez)
├── signals/                 # input.json (runtime, no commitea) + input.example.json + README.md
├── backend/                 # FastAPI (worker backend) — app/ protegida por AGENTS.md
│   ├── Dockerfile (python:3.11-slim + uvicorn)
│   ├── requirements.txt
│   ├── app/                 # main.py, api/v1/, modelos, servicios
│   └── alembic/             # Migraciones (crean las TABLAS)
├── frontend/                # SPA React (worker frontend) — src/ protegida por AGENTS.md
│   ├── Dockerfile (multietapa node:20-alpine → nginx:alpine)
│   ├── nginx.conf           # SPA fallback + proxy /api/ → api:8000
│   └── src/                 # pages/, lib/api.ts, componentes shadcn
├── scraper/                 # Playwright → /scrape, /health (:5000)
│   ├── Dockerfile (python:3.11-slim-bookworm + playwright install --with-deps chromium)
│   ├── requirements.txt     # + playwright==1.49.0
│   └── app.py
├── n8n/workflows/           # 01-radar-scrape.json · 02-dedup-score.json · 03-signal-catcher.json · 04-crm-sync.json · 05-linkedin-signals.json
└── docs/                    # Esta base de conocimiento (PKM) + docs conceptuales previas
```

## Servicios Docker

| Servicio | Imagen/build | Puerto host→cont | Perfil |
|---|---|---|---|
| `db` | `postgis/postgis:16-3.5` | 5432→5432 | base |
| `redis` | `redis:7-alpine` | — | base |
| `api` | `./backend` (python:3.11-slim) | 8000→8000 | base |
| `web` | `./frontend` (node:20-alpine → nginx:alpine) | 3000→80 | base |
| `n8n` | `n8nio/n8n` (2.35.7) | 5678→5678 | `automation` |
| `scraper` | `./scraper` | 5000→5000 | `automation` |
| `cloudflared` | `cloudflare/cloudflared` | — | `tunnel` |

## Endpoints HTTP

### API backend (`/api/v1`)

16 routers: `company`, `catalogs`, `analysis`, `ai`, `leads`, `investigations`, `territories`, `system`, `signals`, `reports`, `providers`, `proposals`, `pipelines`, `etl`, `geo_weather`, `geo` (`_common` helpers). Documentación interactiva: `http://localhost:8000/docs`. Detalle en [api/rest.md](api/rest.md).

### Scraper (`:5000`)

- `POST /scrape` — body con query de Google Maps + `max_results`; devuelve leads crudos.
- `GET /health`.

### n8n (`:5678`)

- UI/editor + API propia (requiere `N8N_API_KEY` para automatización externa).
- Ejecución CLI: `docker exec -e N8N_RUNNERS_BROKER_PORT=5680 geis-n8n n8n execute --id <workflowId>`.

## Workflows n8n (módulo Radar)

| Archivo | Stage | Trigger |
|---|---|---|
| `01-radar-scrape.json` | `radar-01` | triple (webhook/manual/CLI) |
| `02-dedup-score.json` | `radar-02` | triple |
| `03-signal-catcher.json` | `radar-03` | triple |
| `04-crm-sync.json` | `radar-04` | triple |
| `05-linkedin-signals.json` | `radar-05` | triple |

Credenciales n8n (nombres): `Postgres GEIS` (ssl `"disable"`), `Apollo API`, `HubSpot`.

## Bases de datos y esquemas

- `prod`: `leads`, `runs`, `providers`, `warm_signals`, `linkedin_stats`, `denue_establishments`, `user_investigations`, + tablas GEIS (territorios, reportes, propuestas, censo…).
- `stg`: `leads_raw`.
- `quarantine`: rechazos de validación.

## Servicios externos

| Servicio | Uso | Credencial (nombre de variable) |
|---|---|---|
| Apollo.io | Enriquecimiento de leads (modo cloud) | `APOLLO_API_KEY` |
| HubSpot | CRM espejo (modo cloud) | `HUBSPOT_TOKEN` |
| LinkedIn Community Management | Señales de página de empresa | `LINKEDIN_CLIENT_ID/SECRET/REDIRECT_URI` u `LINKEDIN_ACCESS_TOKEN` |
| Apify | Scrapeo cloud alternativo | `APIFY_TOKEN` (plan FREE) |
| Open-Meteo | Temperatura para scoring (gratis) | — |
| Google Maps | Fuente de scrapeo (vía Playwright) | — |
| INEGI DENUE | Refresco de establecimientos | `DENUE_API_TOKEN` |
| Proveedores IA del asistente (opcional) | Hasta 5: OpenAI, Anthropic, Gemini, Groq, DeepSeek | claves generadas por el wizard **Configurar empresa** |

## Variables de entorno requeridas (nombres solo)

`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`, `REDIS_URL`, `DENUE_API_TOKEN`, `SECRET_KEY`, `VITE_API_URL`, `N8N_URL`, `N8N_API_KEY`, `N8N_ENCRYPTION_KEY`, `SCRAPER_URL`, `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI`, `LINKEDIN_ACCESS_TOKEN`, `APOLLO_API_KEY`, `APIFY_TOKEN`, `HUBSPOT_TOKEN`, + claves IA opcionales. Fuente de verdad: `.env.example` (ver [environment.md](environment.md)).

## Volúmenes

- `pgdata` (Postgres) — el backup `backup_pg15_20261019_2059.sql` se tomó antes de recrearlo en el upgrade a PostGIS 16-3.5.
- `n8n_data` (SQLite + credenciales cifradas de n8n).
- Bind mount `./signals` → `/signals` (lectura del paso 03, restringida por `N8N_RESTRICT_FILE_ACCESS_TO`).
