# GEIS — Entorno (reconstruible)

Fecha de captura: 2026-10-21.

## Host

- Windows (PowerShell 5.1), drive `F:\` para el proyecto, `C:\Users\mauri` home.
- Docker Engine **29.7.2** (build a7dcaa6), Docker Compose **v5.4.0** (plugin v2).
- Git **2.43.0.windows.1**.

## Contenedores (versiones fijadas)

| Componente | Versión |
|---|---|
| PostgreSQL + PostGIS | `postgis/postgis:16-3.5` |
| Redis | `redis:7-alpine` |
| Python (api) | 3.11-slim |
| Python (scraper) | 3.11-**slim-bookworm** (requerido por deps de Playwright) |
| Playwright | 1.49.0 (+ Chromium instalado en build) |
| n8n | 2.35.7 |
| Node (build frontend) | node:20-alpine |
| Nginx (serve frontend) | nginx:alpine |

## Stack backend

FastAPI ≥0.110, uvicorn[standard] ≥0.29, Pydantic ≥2.5, SQLAlchemy ≥2.0, GeoAlchemy2 ≥0.14, psycopg2-binary ≥2.9, Shapely ≥2.0, pyproj ≥3.6, httpx ≥0.27, python-dotenv ≥1.0, Alembic ≥1.13, NumPy ≥1.26, SciPy ≥1.12, python-frontmatter ≥1.0; testing: pytest ≥8.0, pytest-asyncio ≥0.23.

## Stack frontend

React 18.3.1, react-router-dom 6.26.2, Vite 5.4.8, TypeScript 5.5.4, Tailwind CSS 3.4.12 (+ PostCSS, Autoprefixer), Radix UI (shadcn), @tanstack/react-table 8.20.5, ECharts 5.5.1 + echarts-for-react 3.0.2, Leaflet 1.9.4 + react-leaflet 4.2.1 + @geoman-io/leaflet-geoman-free 2.17.0, zustand 4.5.5, sonner 1.5.0, class-variance-authority, clsx, tailwind-merge.

> ⚠️ Asumido: `package.json` usa rangos `^`; las versiones listadas son los mínimos declarados, no las exactas instaladas en `node_modules`.

## Red / puertos

- Red `geis-net` interna. Host: 3000 (web), 8000 (api), 5678 (n8n), 5000 (scraper), 5432 (db).
- URLs internas Docker: `N8N_URL=http://n8n:5678`, `SCRAPER_URL=http://scraper:5000`, `DATABASE_URL=postgresql+psycopg2://geis:***@db:5432/geis`, `REDIS_URL=redis://redis:6379/0`.

## Servicios externos del análisis de ubicaciones (sin llave)

| Servicio | Variable | Default | Fallback si falla |
|---|---|---|---|
| Nominatim/OSM (geocoding) | — | `https://nominatim.openstreetmap.org` | `POST /territories/geocode` → **422** (nunca un punto falso) |
| Valhalla/OSM (isócronas) | `VALHALLA_BASE_URL` | `https://valhalla1.openstreetmap.de` | `area_alcance_tiempo.alcance_tipo="radios"` |
| Overpass/OSM (vialidades) | — | `https://overpass-api.de/api/interpreter` | lista vacía; el proxy vehicular usa basal poblacional (declarado) |

- Todos usan `User-Agent: GEIS/1.0 (geis-local)` y timeouts de 10–15 s.
- Overpass puede responder **502** por capacidad; el reporte sigue siendo válido y lo declara (no inventa vialidades).
- `VALHALLA_BASE_URL` es opcional: si se define una instancia propia, se usa esa.

## Migraciones vigentes

- Revisión **0006 (head)**: `0005` agrega `entidad/municipio/colonia/cp/scian` + índices a `prod.leads`; `0006` crea `prod.report_shares` y `prod.user_investigations.es_principal`.
- Verificar con `docker compose exec api alembic current`; aplicar con `make migrate`.

## Configuración sensible de n8n (crítico)

- `N8N_ENCRYPTION_KEY`: 64 hex, generada UNA vez (PowerShell: `-join ((1..64) | % { '{0:x}' -c (Get-Random -Max 16) })`). Jamás rotarla sin re-importar credenciales.
- `N8N_RESTRICT_FILE_ACCESS_TO=/signals`: único path legible por nodos de archivo.
- Ejecución CLI de workflows con Code nodes: `docker exec -e N8N_RUNNERS_BROKER_PORT=5680 geis-n8n n8n execute --id <id>` (evita conflicto de puerto del Task Broker con el runner interno).

## Codificación

- Todos los JSON que consumen nodos n8n/PowerShell deben ser **UTF-8 sin BOM** (el BOM produce `Unexpected token '~'` / `'﻿'` en `JSON.parse`).
