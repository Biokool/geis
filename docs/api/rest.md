# GEIS — API REST (`/api/v1`)

Fuente de verdad interactiva: <http://localhost:8000/docs> (OpenAPI 3). Este documento es el mapa funcional + reglas operativas descubiertas en operación real (límites, paginación, gating).

## Reglas transversales

- **Auth**: ninguna en local (JWT firmado con `SECRET_KEY` pero sin guard); habilitar antes de exponer.
- **Paginación por cursor** (`/leads*`): `limit` **≤ 100** (`FastAPI Query(le=100)`) + `cursor`/`next_cursor`. No hay `total` — contar exige iterar. `/pipelines/runs` acepta `limit` hasta **200**.
- **Errores contractuales conocidos**: `422` si `limit>100` en `/leads*`; `409` si se viola el gating de pipelines; `500` si `prod.runs.detalle` no es dict (ADR-005).
- Todo CRUD de leads habla con `prod.leads` (curados) y `stg.leads_raw` (crudos).

## Endpoints por router

### `/leads` — leads del Radar

| Método | Path | Descripción |
|---|---|---|
| GET | `/api/v1/leads` | Página de leads (crudos+curados) con cursor. `limit≤100` → `422` si excede |
| GET | `/api/v1/leads/curados` | Leads curados (dedup, geocodificados, scorados). Devuelve `lat`/`lon`, `etapa`, `score`, `linea`, `enriquecido_apollo`, `crm_synced_at` |
| GET | `/api/v1/leads/curados/{lead_id}` | Detalle de un lead curado |
| PATCH | `/api/v1/leads/curados/{lead_id}` | Edición SDR (etapa del pipeline, notas, datos de contacto) |
| POST | `/api/v1/leads/export?formato=csv` | Export CSV (tope 5,000 filas; `formato=excel` → 501) |

### `/pipelines` — orquestación del Radar

| Método | Path | Descripción |
|---|---|---|
| POST | `/api/v1/pipelines/run/{stage}` | Lanza un stage (`radar-01..05`, `etl-denue`, `etl-censo`). **409** si el paso anterior no terminó OK. Crea fila en `prod.runs` |
| GET | `/api/v1/pipelines/runs` | Bitácora de corridas (`limit≤200`). Requiere `detalle` dict en todas las filas |
| PATCH | `/api/v1/pipelines/runs/{run_id}` | Actualiza estado/detalle de una corrida (lo usa el workflow al finalizar) |
| GET | `/api/v1/pipelines/workflows` | Catálogo de workflows disponibles (para la UI de Operación) |

### `/providers` — capa anti-cautiverio

| Método | Path | Descripción |
|---|---|---|
| GET | `/api/v1/providers` | Lista de providers con su modo (`local`/`cloud`/`disabled`) y estado |
| GET | `/api/v1/providers/{name}` | Detalle (`scraper`, `enrichment`, `crm`, `email`, `weather`, `linkedin`, `geocoding`, `routing`) |
| PUT | `/api/v1/providers/{name}` | Conmuta modo/provider/config. Body: `{"mode":"local\|cloud\|disabled","provider":"...","config":{...},"enabled":bool}` |

### `/integrations/linkedin` — OAuth Community Management

| Método | Path | Descripción |
|---|---|---|
| GET | `/api/v1/integrations/linkedin/auth` | Inicia el flujo OAuth (redirect a LinkedIn) |
| GET | `/api/v1/integrations/linkedin/callback` | Callback OAuth (canjea `code` por token) |
| GET | `/api/v1/integrations/linkedin/status` | `connected`, scopes, org, expiración |
| POST | `/api/v1/integrations/linkedin/disconnect` | Limpia el token del provider |

### `/signals` — señales del SDR

| Método | Path | Descripción |
|---|---|---|
| POST | `/api/v1/signals` | Registra una señal cálida (la UI SDR y el workflow 03 la usan) |

### `/analysis` — inteligencia GEIS

| Método | Path | Descripción |
|---|---|---|
| POST | `/api/v1/analysis/location` | Análisis de ubicación (ISM, Huff, TAM, veredicto) |
| POST | `/api/v1/analysis/b2b-prospecting` | Prospección B2B de zona |
| POST | `/api/v1/analysis/lookalike` | Establecimientos similares a una referencia |

### `/investigations` / `/reports` / `/proposals` / `/territories` / `/catalogs` / `/etl` / `/geo` / `/system` / `/company` / `/ai`

| Router | Endpoints | Notas |
|---|---|---|
| `/territories` | `POST /geocode` | Geocodificación |
| `/reports` | `POST /`, `GET /{id}` | Reportes de viabilidad; **PDF es fase 2** (tooltip honesto en UI) |
| `/investigations` | `POST /`, `GET /`, `GET /{id}` | Investigaciones guardadas; hoy 0 filas → Historial vacío legítimo; `DELETE` es fase 2 |
| `/proposals` | CRUD completo (`POST`, `GET`, `GET/{id}`, `PATCH/{id}`, `DELETE/{id}`) | Propuestas comerciales |
| `/catalogs` | `GET /scian` | Catálogo SCIAN |
| `/etl` | `GET /status` | Estado de ETLs DENUE/Censo |
| `/geo` | `GET /weather` | Clima (Open-Meteo, caché 6 h) para scoring |
| `/system` | `GET /health` | Salud integral del stack |
| `/company` | `GET /profile`, `PUT /profile`, `POST /profile/derive`, `POST /profile/activate/{id}`, `GET /profiles` | Wizard de configuración de empresa (perfil, derivación de vertical) |
| `/ai` | `GET /status`, `POST /chat`, `POST /fill-profile` | Asistente IA (hasta 5 proveedores configurables; "Llenar con IA" del wizard) |

## Contratos de datos clave (interfaces TS espejo en `frontend/src/lib/api.ts`)

`LeadCurado` incluye: identificación, contacto, `lat/lon`, `etapa` (nuevo→contactado→reunión→propuesta→ganado/perdido), `score`, `linea`, `temp_zona`, `enriquecido_apollo?: boolean`, `crm_synced_at?: string | null`.

`RunOut`: `run_id`, `stage`, `status` (`ok|error|running`), `detalle: dict` (obligatorio objeto JSON).

## Ejemplos de uso probados (2026-10-21)

```powershell
# Paginar todos los leads curados
$cur = $null; $items = @()
do {
  $url = "http://localhost:3000/api/v1/leads/curados?limit=100" + $(if ($cur) { "&cursor=$cur" } else { "" })
  $r  = Invoke-RestMethod $url; $items += $r.items; $cur = $r.next_cursor
} while ($cur)   # $items.Count == 160

# Lanzar el paso 02 (falla 409 si 01 no terminó OK)
Invoke-RestMethod -Method Post http://localhost:3000/api/v1/pipelines/run/radar-02
```
