# GEIS — Instalación desde cero

Objetivo: levantar el stack completo (GEIS + módulo Radar) en una máquina limpia con Docker.

## Requisitos

- Docker Engine 24+ con plugin Docker Compose v2 (`docker compose version`).
- ~6 GB RAM libres (n8n suma ~400 MB; scraper con Chromium ~2 GB de disco de imagen).
- Puertos libres: 3000, 8000, 5432, 5000, 5678.

## Pasos

```powershell
# 1. Clonar el repo y entrar
cd F:\__AGENCIA_AIMA\__MUSE\Geointeligencia\geis

# 2. Variables de entorno
Copy-Item .env.example .env
# Editar .env:
#  - SECRET_KEY y POSTGRES_PASSWORD: obligatorio cambiar en producción
#  - N8N_ENCRYPTION_KEY: generar UNA vez (64 hex). PowerShell:
#      -join ((1..64) | % { '{0:x}' -c (Get-Random -Max 16) })
#  - APOLLO_API_KEY, HUBSPOT_TOKEN, APIFY_TOKEN, LINKEDIN_*, DENUE_API_TOKEN: opcionales
#    (vacíos = provider se queda en modo local/disabled)

# 3. Servicios base
docker compose up --build -d

# 4. Tablas (Alembic) y datos de muestra
make migrate   # docker compose exec api alembic upgrade head
make seed      # docker compose exec api python -m app.seed

# 5. (Opcional) orquestador del Radar + scraper
make n8n       # docker compose --profile automation up -d n8n
docker compose --profile automation up -d --build scraper
```

## Verificación

| Chequeo | Comando / URL | Esperado |
|---|---|---|
| Contenedores sanos | `docker compose ps` | db, redis, api, web (y n8n, scraper) `healthy` |
| API | `http://localhost:8000/docs` | Swagger UI |
| Web | `http://localhost:3000` (Ctrl+F5) | Dashboard Inicio con KPIs |
| n8n | `http://localhost:5678` | Editor con los 5 workflows |
| Scraper | `curl http://localhost:5000/health` | `ok` |
| Leads | `curl "http://localhost:3000/api/v1/leads/curados?limit=100"` | JSON con items + next_cursor |
| Runs | `curl "http://localhost:3000/api/v1/pipelines/runs?limit=20"` | Bitácora de corridas (200 OK) |

## Importar los workflows de n8n (solo primera vez o tras reset de `n8n_data`)

> Los workflows ya viven en el volumen `n8n_data` con sus IDs y credenciales. Estos pasos son para reconstruir.

```powershell
# 1. Credenciales (crear JSON temporales UTF-8 SIN BOM, un archivo por credencial)
docker exec -i geis-n8n n8n import:credentials --input=/path/cred.json
#    - "Postgres GEIS": host=db, db=geis, user=geis, ssl="disable" (STRING, no boolean)
#    - "Apollo API" y "HubSpot": headers Authorization con el token del .env

# 2. Workflows (upsert por top-level id; los JSON ya traen Nanoids y referencias de credencial)
docker exec -i geis-n8n n8n import:workflow --input=/workflows/01-radar-scrape.json
#    repetir por archivo (import por archivo evita EISDIR de --separate en Windows)
```

## Configuración inicial de negocio

1. Abrir `http://localhost:3000` → banner **"Aún no configuras tu empresa"** → wizard de 4 pasos (giro, perfil `PERFIL-EMPRESA.md`, API keys IA opcionales, resumen).
2. Sistema → Providers: conmutar `enrichment`→cloud/apollo y `crm`→cloud/hubspot según se disponga de credenciales.
3. LinkedIn: flujo OAuth (ver [deployment.md](deployment.md#integración-linkedin)).

## Problemas conocidos del primer arranque

- **422 en `/leads`**: el backend cap `limit≤100`; el frontend ya lo respeta — cualquier cliente custom debe paginar por `next_cursor`.
- **500 en `/pipelines/runs`**: si `prod.runs.detalle` tiene arrays o NULL (p. ej. por updates manuales), normalizar (ADR-005).
- **n8n crash-loop**: `N8N_ENCRYPTION_KEY` distinta a la que cifró las credenciales del volumen.
- **"Access to the file is not allowed"** en radar-03: verificar `N8N_RESTRICT_FILE_ACCESS_TO=/signals` en docker-compose.
- **BOM**: cualquier JSON generado en Windows para n8n debe guardarse UTF-8 sin BOM.
