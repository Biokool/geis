# Scraper de Google Maps — provider `scraper` del ecosistema GEIS

Microservicio Flask + Playwright. Es la **implementación del provider `scraper`**
del ecosistema (ver `docs/ECOSISTEMA-FUSION.md` §3): el workflow n8n
`01-radar-scrape` lo llama y los resultados aterrizan en `stg.leads_raw`.

```
POST http://scraper:5000/scrape
{ "query": "bodegas", "location": "Toluca, Estado de México", "max_results": 40 }
```

Devuelve `{ ok, backend, count, results: [{nombre, direccion, telefono, web, rating, lat, lng, url}] }`.

## Endpoints

| Método | Ruta      | Descripción |
|--------|-----------|-------------|
| `GET`  | `/health` | `{ ok, servicio, mode, provider, apify_token }` — útil para el semáforo de Sistema. |
| `POST` | `/scrape` | Scrapea Google Maps. Body: `query` (requerido), `location`, `max_results` (1–60, default 40). Flag opt-in `"guardar": true` → además inserta los resultados en `stg.leads_raw` (con `geom` PostGIS 4326) y devuelve `guardados`. |

El flujo normal **no** usa `guardar`: el workflow 01 de n8n normaliza e inserta
en `stg.leads_raw` él mismo (dedup dentro del lote). El flag existe para probar
el scraper sin n8n o para ingestas puntuales.

## Backends (anti-cautiverio)

El backend se elige **por request** leyendo `prod.providers` (`name='scraper'`,
caché de 60 s):

- `mode=local` → Playwright con Chromium headless (default, $0).
- `mode=cloud`, `provider=apify` → actor `apify/google-maps-scraper` (requiere `APIFY_TOKEN`).
- Override por entorno para pruebas: `SCRAPER_PROVIDER=local|apify`.

Se cambia sin reiniciar desde Sistema → Proveedores.

## Variables de entorno

| Variable            | Default              | Descripción |
|---------------------|----------------------|-------------|
| `DATABASE_URL`      | (ver abajo)          | URL Postgres GEIS, p. ej. `postgresql+psycopg2://geis:***@db:5432/geis`. Prioritaria: de aquí sale la conexión para leer `prod.providers` y para `guardar`. |
| `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`/`PGDATABASE` | `db`/`geis`/`geis` | Solo si no hay `DATABASE_URL`. |
| `APIFY_TOKEN`       | (vacío)              | Token de Apify para el backend nube. |
| `SCRAPER_PROVIDER`  | (vacío)              | `local` o `apify`: fuerza el backend sin tocar la base. |

## Nota honesta sobre bloqueos

Scrapear Google Maps vive en zona gris: sus términos lo desalientan y el
scraping agresivo provoca CAPTCHAs o bloqueos de IP. Este servicio está
diseñado para volúmenes modestos y responsables:

- Delays aleatorios de 2–5 s entre páginas y fichas.
- Máximo 3 páginas de resultados por búsqueda (~60 fichas tope).
- Una sola corrida semanal (lunes 6am, workflow 01).

Si Google empieza a bloquear: baja `max_results`, espacía las corridas o
cambia a la **Places API oficial** (tiene capa gratuita mensual generosa y
es 100% legítima; requiere API key de Google Cloud). El provider conmuta sin
tocar los pipelines (riesgo R-01 del blueprint).

## Probar a mano

```bash
curl -X POST http://localhost:5000/scrape \
  -H 'Content-Type: application/json' \
  -d '{"query":"bodegas","location":"Toluca","max_results":5}'

# con escritura directa a staging (sin n8n):
curl -X POST http://localhost:5000/scrape \
  -H 'Content-Type: application/json' \
  -d '{"query":"bodegas","location":"Toluca","max_results":5,"guardar":true}'
```
