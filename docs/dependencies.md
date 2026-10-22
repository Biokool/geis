# GEIS — Dependencias

## Política de versionado

- Backend/scraper: rangos semver en `requirements.txt` (pip resuelve al build).
- Frontend: rangos `^` en `package.json`; lockfile no commiteado (imagen se construye en Docker).
- Infraestructura: imágenes fijadas por tag en `docker-compose.yml`.

## Runtime — backend (`backend/requirements.txt`)

| Paquete | Rango | Propósito |
|---|---|---|
| fastapi | ≥0.110,<1 | Framework API |
| uvicorn[standard] | ≥0.29 | Servidor ASGI |
| pydantic | ≥2.5 | Validación (modelos estrictos, p. ej. `RunOut.detalle: dict`) |
| sqlalchemy / geoalchemy2 | ≥2.0 / ≥0.14 | ORM + tipos geográficos |
| psycopg2-binary | ≥2.9 | Driver Postgres |
| shapely / pyproj | ≥2.0 / ≥3.6 | Geometría y proyecciones (modelos espaciales) |
| httpx | ≥0.27 | Cliente HTTP (n8n, nube, Open-Meteo) |
| python-dotenv | ≥1.0 | Carga `.env` |
| alembic | ≥1.13 | Migraciones de esquema |
| numpy / scipy | ≥1.26 / ≥1.12 | Cálculo numérico (Huff, ISM, TAM) |
| python-frontmatter | ≥1.0 | Parsing de `PERFIL-EMPRESA.md` |
| pytest / pytest-asyncio | ≥8.0 / ≥0.23 | Suite de tests |

## Runtime — scraper (`scraper/requirements.txt`)

- Flask/HTTP server + **playwright==1.49.0** (pinned exacto; se instaló para el scrapeo headless de Google Maps con Chromium).

## Runtime — frontend (`frontend/package.json`)

Ver [environment.md](environment.md). Grupos funcionales:

- **UI**: react, react-dom, react-router-dom, Radix UI (24 primitivos), sonner (toasts), class-variance-authority + clsx + tailwind-merge (utilidades shadcn).
- **Datos/tabla**: @tanstack/react-table, zustand (estado global).
- **Gráficos**: echarts + echarts-for-react (dashboard de Inicio: embudo y dona).
- **Mapa**: leaflet, react-leaflet, @geoman-io/leaflet-geoman-free (dibujo de zonas).
- **Build**: vite, @vitejs/plugin-react, typescript, tailwindcss + postcss + autoprefixer.

## Sistema (dentro de las imágenes)

- PostGIS 16-3.5 (extensiones `postgis`, `pg_trgm`, `uuid-ossp`).
- Chromium + deps de sistema (vía `playwright install --with-deps`) en el scraper (~2.1 GB de imagen).
- Nginx alpine (serving SPA + proxy `/api/`).

## Servicios externos (dependencias de operación, no de código)

| Servicio | Modo provider | Notas |
|---|---|---|
| Apollo.io | `enrichment` cloud | API key validada (`healthy/logged_in`) |
| HubSpot | `crm` cloud | Token + propiedades custom `biokool_etapa/score/linea`; scope extra `crm.schemas.custom.write` |
| LinkedIn | `linkedin` cloud | OAuth Community Management; org `107784991` (vanity `biokool`) |
| Apify | `scraper` cloud (alternativa) | Plan FREE |
| Open-Meteo | `weather` local | Sin clave; caché 6 h |
| INEGI DENUE | etl externo | `DENUE_API_TOKEN` opcional |

## Cambios de dependencia recientes

- **Añadido**: `playwright==1.49.0` (scraper) + base `python:3.11-slim-bookworm` — habilita el scrapeo real del paso `radar-01`. Impacto: imagen scraper ~2.1 GB.
- **Upgrade infra**: `postgis/postgis:15-3.4` → `16-3.5` (volumen recreado; ver [ADR-001](decisions/ADR-001-postgis-16-35.md)).
- **Añadido (frontend, ya existían)**: `enriquecido_apollo` y `crm_synced_at` en la interfaz TS `LeadCurado` (`frontend/src/lib/api.ts`) — no son dependencias nuevas, sí superficie de datos nueva.
