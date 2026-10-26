# GEIS — API REST (`/api/v1`)

Fuente de verdad interactiva: <http://localhost:8000/docs> (OpenAPI 3). Este documento es el mapa funcional + reglas operativas descubiertas en operación real (límites, paginación, gating). **Última verificación E2E contra PostGIS real: 2026-10-25.**

## Reglas transversales

- **Auth**: ninguna en local (JWT firmado con `SECRET_KEY` pero sin guard); habilitar antes de exponer. El único endpoint pensado para ser público es `GET /reports/shared/{token}` (token opaco, expirable y revocable).
- **Paginación por cursor** (`/leads*`): `limit` **≤ 100** (`FastAPI Query(le=100)`) + `cursor`/`next_cursor`. Las páginas no devuelven `total`; para el conteo exacto existe **`GET /leads/count`**. `/pipelines/runs` acepta `limit` hasta **200**.
- **Filtros geográficos** (`/leads`, `/leads/curados`, `/leads/count`): `entidad`, `municipio`, `colonia`, `cp`, `scian` (columnas derivadas por la migración 0005). La cascada de valores disponibles está en `GET /catalogs/geo-filters`.
- **Errores contractuales conocidos**: `422` si `limit>100` o si el geocoding no resuelve; `409` si se viola el gating de pipelines; `404` en shares inválidos/expirados/revocados; `500` si `prod.runs.detalle` no es dict (ADR-005).
- Todo CRUD de leads habla con `prod.leads` (curados) y `stg.leads_raw` (crudos).

## Endpoints por router

### `/leads` — leads del Radar

| Método | Path | Descripción |
|---|---|---|
| GET | `/api/v1/leads` | Página de leads (crudos+curados) con cursor y filtros geo. `limit≤100` → `422` si excede |
| GET | `/api/v1/leads/count` | **Total exacto** de `prod.leads` (filtros `etapa`, `linea`, `source` + geo). Usado por el badge del menú, KPIs y Panel Radar |
| GET | `/api/v1/leads/curados` | Leads curados (dedup, geocodificados, scorados). Devuelve `lat`/`lon`, `etapa`, `score`, `linea`, `entidad/municipio/colonia/cp/scian`, `enriquecido_apollo`, `crm_synced_at`; acepta los 5 filtros geo |
| GET | `/api/v1/leads/curados/{lead_id}` | Detalle de un lead curado (`lat/lon`, dirección, contacto, notas, etapa) |
| PATCH | `/api/v1/leads/curados/{lead_id}` | Edición SDR (etapa del pipeline, notas, datos de contacto). `etapa=ganado` alimenta `knowledge_facts` |
| POST | `/api/v1/leads/enrich-geo` | Deriva `entidad/municipio/colonia/cp/scian` (AGEB por contención + DENUE ≤500 m + **fallback de dirección formateada** — ver ADR-009). Body `{"limite": 500}` opcional. Idempotente (`COALESCE`); `detalle.solo_cp` = sin geometría con algún dato del texto, `sin_datos` = sin nada |
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
| POST | `/api/v1/analysis/compare` | Compara **2–6** items: `{"items":[{"investigation_id":"..."}]}` o puntos directos `{"items":[{"lat":19.42,"lon":-99.16,"giro":"Cafetería","scian":"722515","etiqueta":"Roma"}]}`. Devuelve veredicto, ISM, competencia, población, TAM y Huff. También acepta `investigation_ids` (legacy, 2–5) |
| POST | `/api/v1/analysis/b2b-prospecting` | Prospección B2B de zona |
| POST | `/api/v1/analysis/lookalike` | Establecimientos similares a una referencia |

### `/investigations` — historial del comparador

| Método | Path | Descripción |
|---|---|---|
| POST | `/api/v1/investigations` | Crea investigación (`investigation_type` ∈ `location_viability`, `b2b_prospecting`, `lookalike`, `multi_compare`, `real_estate`) |
| GET | `/api/v1/investigations` | Lista (más recientes primero; `limit≤100`) |
| GET | `/api/v1/investigations/{id}` | Detalle |
| PATCH | `/api/v1/investigations/{id}` | `{"title"?: string, "es_principal"?: bool}`; la ganadora persiste por usuario y desmarca las demás |
| DELETE | `/api/v1/investigations/{id}` | **204**, borrado físico (hijas de `investigation_leads` por CASCADE) |

### `/reports` — reportes de ubicación

| Método | Path | Descripción |
|---|---|---|
| POST | `/api/v1/reports` | Genera y persiste el reporte completo. Body: `title`, `giro`, `scian`, `lat`, `lon`, `radios`, `investigation_id?` y overrides TAM opcionales `gasto_promedio_mensual`, `f_nse`, `f_pen` |
| GET | `/api/v1/reports/{id}` | Lee el JSON persistido (24 claves: veredicto, clientes, hogares, atractores, competencia, mapas, entorno, población, movimiento, isócronas, modelos, sector, anclas, delivery, break-even, plan y fuentes) |
| POST | `/api/v1/reports/{id}/share` | **201** Crea link invitado. Body `{"dias":30}` (1–365). Devuelve `token`, `url=/r/{token}`, `expira_en` |
| GET | `/api/v1/reports/shared/{token}` | **Público, solo lectura**; **404** si expiró o fue revocado |
| DELETE | `/api/v1/reports/{id}/share/{token}` | **204** Revoca el token (el GET público pasa a 404) |

> El «PDF» del reporte no es un endpoint: es la vista imprimible `/reporte/{id}/imprimir` (CSS print + «Guardar como PDF» del navegador). `GET /reports/{id}/pdf` sigue siendo fase 2 y la UI lo dice con tooltip honesto.

### `/territories` — geocoding real

| Método | Path | Descripción |
|---|---|---|
| POST | `/api/v1/territories/geocode` | Body `{"lat":19.43,"lon":-99.13}` **o** `{"address":"..."}`. Acepta coordenadas, links de Google Maps (`@lat,lon`, `!3d!4d`, `?q=`, links cortos `maps.app.goo.gl`) o dirección en texto (Nominatim, solo MX). Devuelve `lat/lon`, `label`, `fuente` (`coordenadas\|link_maps\|nominatim`), `direccion_formateada`, `colonia/municipio/entidad/cp`. **422 si no resuelve** (nunca un punto falso) |

### `/catalogs` / `/etl` / `/geo` / `/system` / `/company` / `/ai` / `/proposals`

| Router | Endpoints | Notas |
|---|---|---|
| `/catalogs` | `GET /geo-filters`, `GET /scian` | `geo-filters` devuelve `entidades`, `municipios`, `colonias`, `cps`, `scians` (cascada desde leads y DENUE). `scian` es el catálogo con intensidad térmica |
| `/etl` | `GET /status` | Estado de ETLs DENUE/Censo |
| `/geo` | `GET /weather` | Clima (Open-Meteo, caché 6 h) para scoring |
| `/system` | `GET /health` | Salud integral del stack |
| `/company` | `GET /profile`, `PUT /profile`, `POST /profile/derive`, `POST /profile/activate/{id}`, `GET /profiles` | Wizard de configuración de empresa |
| `/ai` | `GET /status`, `POST /chat`, `POST /fill-profile` | Asistente IA (hasta 5 proveedores configurables) |
| `/proposals` | CRUD completo | Propuestas comerciales (API lista; sin pantalla que la consuma todavía) |

## Contratos de datos clave (interfaces TS espejo en `frontend/src/lib/api.ts` y `apiGeo.ts`)

`LeadCurado` incluye: identificación, contacto, `lat/lon`, `etapa` (nuevo→contactado→reunión→propuesta→ganado/perdido), `score`, `linea`, `temp_zona`, `entidad/municipio/colonia/cp/scian`, `enriquecido_apollo?: boolean`, `crm_synced_at?: string | null`.

`RunOut`: `run_id`, `stage`, `status` (`ok|error|running`), `detalle: dict` (obligatorio objeto JSON).

`SharedReportOut`: `report_id`, `title`, `verdict`, `payload`, `expira_en` — sin lineage ni datos internos.

## Ejemplos de uso probados (2026-10-25)

```powershell
# Paginar todos los leads curados (sigue sirviendo; para contar usa /leads/count)
$cur = $null; $items = @()
do {
  $url = "http://localhost:3000/api/v1/leads/curados?limit=100" + $(if ($cur) { "&cursor=$cur" } else { "" })
  $r  = Invoke-RestMethod $url; $items += $r.items; $cur = $r.next_cursor
} while ($cur)   # $items.Count == 160

# Conteo exacto y filtros geográficos
Invoke-RestMethod http://localhost:3000/api/v1/leads/count
Invoke-RestMethod "http://localhost:3000/api/v1/leads/count?entidad=Ciudad%20de%20M%C3%A9xico"
Invoke-RestMethod http://localhost:3000/api/v1/catalogs/geo-filters

# Geocoding de un link de Maps (sin red) y de una dirección (Nominatim)
$b = @{address='https://www.google.com/maps/@19.4326,-99.1332,17z'} | ConvertTo-Json
Invoke-RestMethod -Method Post http://localhost:3000/api/v1/territories/geocode `
  -ContentType 'application/json' -Body ([Text.Encoding]::UTF8.GetBytes($b))

# Lanzar el paso 02 (falla 409 si 01 no terminó OK)
Invoke-RestMethod -Method Post http://localhost:3000/api/v1/pipelines/run/radar-02
```

> **Acentos en PowerShell:** `Invoke-RestMethod -Body` con un string se envía en Latin-1 y FastAPI responde 400 por JSON inválido. Enviar siempre `[Text.Encoding]::UTF8.GetBytes($json)`.
