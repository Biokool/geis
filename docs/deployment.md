# GEIS — Operación y despliegue (runbook)

## Levantar / detener

```powershell
docker compose up --build -d                  # base: db, redis, api, web
make n8n                                     # + orquestador
docker compose --profile automation up -d --build scraper
docker compose ps                            # salud
docker compose logs -f api                   # logs en vivo
make down                                    # detener sin perder datos
make clean                                   # PELIGRO: borra volúmenes (datos)
```

## Pipeline Radar — orden y gating

Orden obligatorio: **radar-01 → 02 → 03 → 04 → 05** (radar-05 no tiene dependencias). El backend rechaza con **409** un paso si el anterior no terminó OK; la UI (página Operación) muestra el motivo.

- **Por UI**: Operación → ▶ en cada paso.
- **Por API**: `POST /api/v1/pipelines/run/{stage}` con stage `radar-01..05`, `etl-denue`, `etl-censo`.
- **Por CLI n8n** (smoke tests / debug):

```powershell
docker exec -e N8N_RUNNERS_BROKER_PORT=5680 geis-n8n n8n execute --id <workflow-id>
```

> `N8N_RUNNERS_BROKER_PORT=5680` evita el conflicto de puerto del Task Broker cuando se ejecuta CLI contra un contenedor ya corriendo.

### Bitácora y estados

`GET /api/v1/pipelines/runs?limit=20` (máx. 200). Cada fila: stage, status (`ok`/`error`/`running`), `detalle` (**dict JSON, nunca array ni NULL** — ADR-005). Corridas atascadas en `running` de pruebas fallidas se marcan `error` a mano:

```sql
UPDATE prod.runs SET status='error', detalle=jsonb_build_object('error','marcado manual: prueba fallida')
WHERE run_id=<n>;
```

### Qué produce cada paso (estado de referencia, 2026-10-21)

| Paso | Última corrida OK | Efecto |
|---|---|---|
| radar-01 | run 7 | 146 leads crudos en `stg.leads_raw` (procesado=true tras 02) |
| radar-02 | run 20 | `prod.leads` 160; 158 con `temp_zona`; 40 `enriquecido_apollo` |
| radar-03 | run 15 | 3 señales procesadas; +2 leads |
| radar-04 | runs 18–19 | 160/160 leads espejados en HubSpot |
| radar-05 | runs 4–5 | `prod.linkedin_stats` + 1 señal cálida real |

## Providers — conmutación

`PUT /api/v1/providers/{name}` con `{"mode":"local|cloud|disabled", ...}`:

```powershell
# Enriquecimiento Apollo (cloud)
Invoke-RestMethod -Method Put -Uri http://localhost:3000/api/v1/providers/enrichment -Body '{"mode":"cloud","provider":"apollo","config":{}}'

# CRM HubSpot (cloud, habilitado)
Invoke-RestMethod -Method Put -Uri http://localhost:3000/api/v1/providers/crm -Body '{"mode":"cloud","provider":"hubspot","config":{},"enabled":true}'
```

Modo actual: `scraper` local, `enrichment` cloud/apollo, `crm` cloud/hubspot, `weather` local (Open-Meteo), `linkedin` cloud.

## Integración LinkedIn

1. `.env`: `LINKEDIN_CLIENT_ID/SECRET/REDIRECT_URI` (app con Community Management API) **o** `LINKEDIN_ACCESS_TOKEN` directo.
2. OAuth manual (el callback va al backend :8000):
   - Detener la api para liberar el puerto si se corre el callback fuera de Docker: `docker compose stop api`.
   - Autorizar en el browser → copiar `code` del redirect → canjear por token (POST a `https://www.linkedin.com/oauth/v2/accessToken`).
   - Volcar el token en `.env` (`LINKEDIN_ACCESS_TOKEN`) y `docker compose up -d api`.
3. Descubrir `org_id` (Biokool = `107784991`) y configurar el provider:

```powershell
Invoke-RestMethod -Method Put -Uri http://localhost:3000/api/v1/providers/linkedin -Body '{
  "mode":"cloud","provider":"linkedin","enabled":true,
  "config":{"access_token":"<token>","org_id":"107784991","vanity_name":"biokool","expires_at":"<iso>"}
}'
# Verificar: GET /api/v1/integraciones/linkedin/status → connected=true,
# scopes r_organization_social,w_organization_social
```

4. radar-05 lee las estadísticas de la página, detecta picos de engagement y escribe señales cálidas (+score).

## Integración HubSpot — propiedades custom

El paso 04 escribe `biokool_etapa`, `biokool_score`, `biokool_linea` en Companies. Sin ellas, HubSpot responde 400 `PROPERTY_DOESNT_EXIST`.

1. La app privada de HubSpot necesita el scope **`crm.schemas.custom.write`** (se añadió a mano).
2. Creación (una sola vez) vía `POST https://api.hubapi.com/crm/v3/properties/companies` por cada propiedad (name/label/type/group).
3. Después, radar-04 sincroniza en lotes (100 por corrida → segunda corrida completó 160/160).

## Integración Apollo

- `APOLLO_API_KEY` validada vía endpoint propio de Apollo (`healthy/logged_in`).
- El provider `enrichment` en modo cloud/apollo activa la rama de enriquecimiento **dentro de radar-02** (nodos "Merge Apollo"): domains, emails, employee_count, technologies → `enriquecido_apollo=true`.
- Costo: ~900–1,200 créditos/año estimados al ritmo actual.

## Reconstruir el frontend tras cambios

```powershell
docker compose up --build -d web
# verificar bundle nuevo servido:
(Invoke-WebRequest http://localhost:3000/).Content -match 'index-\w+\.js'
```

> Tras cada rebuild: **hard refresh (Ctrl+F5)** en el navegador. Pestañas abiertas con el bundle viejo siguen polleando endpoints inexistentes (p. ej. `/api/runs/activos` 404) y confunden el diagnóstico.

## Migraciones de base de datos

```powershell
make migrate        # alembic upgrade head (aditivo)
docker compose exec api alembic downgrade -1   # rollback puntual
```

Upgrade mayor de Postgres (como 15→16) exige backup (`pg_dump`), recrear el volumen `pgdata`, subir la imagen y re-aplicar migrate+seed (ver [ADR-001](decisions/ADR-001-postgis-16-35.md)).

## Despliegue expuesto (no-local)

- Cambiar `SECRET_KEY`, `POSTGRES_PASSWORD`, y todo token antes de exponer.
- `VITE_API_URL` en el build del frontend si se separa del backend.
- Túnel rápido: `docker compose --profile tunnel up -d cloudflared`.
