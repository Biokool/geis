# n8n — Orquestador del Módulo Radar (GEIS)

Los 5 workflows de `workflows/` son la adaptación a GEIS de los originales de
Biokool Radar (`~/workspace/biokool-radar/n8n/workflows/`). Se importan una vez
en n8n (Workflows → ⋯ → Import from file); el servicio los monta en
`/home/node/workflows` solo como referencia versionada.

**Contrato con la API GEIS** (lo implementa el worker de Fase B; los workflows
ya lo consumen):

| Llamada | Cuándo | Respuesta esperada |
|---------|--------|-------------------|
| `POST http://api:8000/api/v1/pipelines/run/{stage}` con `{"origen":"n8n"}` | Al inicio de cada workflow (`{stage}` = `radar-01`…`radar-05`). Registra el run en `prod.runs` como `running` **y aplica el bloqueo por orden** (si la etapa previa no terminó `ok`, o ya hay un run en curso, responde 409/4xx y el workflow se detiene ahí). | `{"run_id": N, ...}` en 2xx. |
| `PATCH http://api:8000/api/v1/pipelines/runs/{run_id}` con `{"estado":"ok"\|"error","detalle":{...}}` | Al final de cada workflow (nodo `Callback Run OK`). | 2xx. Si falla, no marca error el workflow (el trabajo ya terminó). |

> **Decisión de integración:** el frontend (página Operación, Fase D) debe
> disparar el **webhook de n8n** (`http://n8n:5678/webhook/radar-0X`), no el
> endpoint de la API: el propio workflow llama a `POST …/run/{stage}` al
> inicio, así hay un único registrador de runs y no hay doble conteo. El
> endpoint además debe ser idempotente ante doble llamada (409 si ya hay un
> `running` de esa etapa).

## Qué cambió vs. los originales (y por qué)

### En los 5 workflows

1. **Nodo `Registrar run (GEIS)`** (nuevo, HTTP POST): primera llamada tras los
   triggers. Ejerce el bloqueo por orden contra la API GEIS en vez de que el
   dashboard Express lo hiciera consultando `runs`.
2. **Nodo `¿Run registrado?`** (nuevo, IF): guarda — solo continúa si la API
   devolvió `run_id`. (Si la API responde 409/bloqueo, el nodo HTTP falla y la
   ejecución de n8n queda en error con el motivo: visible y honesto.)
3. **Nodo `Callback Run OK`** (nuevo, HTTP PATCH): reemplaza al `Run OK` que
   hacía `INSERT INTO runs … 'ok'` directo. Ahora el estado final lo escribe
   la API (`prod.runs` tiene columnas distintas: `pipeline`, `estado`,
   `started_at/finished_at`).
4. **Credencial** `Postgres Radar` → `Postgres GEIS` (re-enlazar en n8n al
   importar; apunta al PostGIS del compose).
5. **Tablas con esquema GEIS**: `leads_raw`→`stg.leads_raw`, `leads`→`prod.leads`,
   `providers`→`prod.providers`, `warm_signals`→`prod.warm_signals`,
   `linkedin_stats`→`prod.linkedin_stats`.
6. **PostGIS en vez de lat/lng sueltos**: `stg.leads_raw.geom` y
   `prod.leads.geom` (`Point, 4326`). Los INSERT construyen el punto con
   `ST_SetSRID(ST_MakePoint(lng, lat), 4326)` (NULL si no hay coords); los
   SELECT que necesitaban lat/lng usan `ST_Y(geom)` / `ST_X(geom)`.
7. **`id` → `lead_id`** en `prod.leads` (se mantiene el alias `AS id` en los
   SELECT para no romper las referencias `$json.id` de los nodos Code).

### Por workflow

- **01-radar-scrape**: sin cambios de lógica (arma búsquedas → scrapea →
  normaliza con dedup dentro del lote → `stg.leads_raw`). Triple trigger
  intacto (Manual, lunes 6am, webhook `radar-01`).
- **02-dedup-score**: el INSERT ahora fija `source='gmaps'` y el dedup respeta
  el `UNIQUE(source, nombre, direccion)` de GEIS. Se eliminó la columna
  `sector` del INSERT (no existe en `prod.leads`; era solo etiqueta). En la
  rama Apollo, `empleados` → `empleados_est` (smallint) con tope 32767 en el
  nodo Code. **Schedule agregado**: `Lunes 6:30am` (el blueprint §1.3 lo lista
  con schedule; el original no lo traía) — corre después del 01; el bloqueo por
  orden lo protege de todos modos.
- **03-signal-catcher**: los dos upserts `+25` se reescribieron como CTE
  (`UPDATE … WHERE lower(nombre)=…` y `INSERT … WHERE NOT EXISTS`), porque el
  `ON CONFLICT (nombre, direccion)` original exige un unique que en GEIS es
  `(source, nombre, direccion)`. El match ahora es **global por nombre**
  (cualquier `source`), lo que preserva la regla de negocio "+25 con match".
  `source='manual'` para leads nuevos. Además: `input.json` en GEIS arranca
  vacío, y con cero items n8n no ejecuta el nodo siguiente — por eso
  `Parsear señales` emite `{_sin_senales:true}` si el array está vacío y el
  nuevo IF `¿Señales manuales?` salta directo a leer `warm_signals`.
- **04-crm-sync**: sin cambios de lógica (modo local = fin; nube → HubSpot
  upsert o stub de Twenty). Conserva Manual + Webhook **sin schedule** (es
  bajo demanda, igual que el original).
- **05-linkedin-signals**: sin cambios de lógica (chequeo de token en
  `prod.providers.config` → stats → picos → `warm_signals`). Los INSERT
  dinámicos que armaba el nodo Code ahora llevan el esquema `prod.`. Requiere
  app real de LinkedIn con Community Management API (riesgo R-02 del
  blueprint; no verificable en este entorno).

## Notas y pendientes honestos

- Los webhooks responden `onReceived` (inmediato); el progreso se sigue en la
  página Operación (Fase D) leyendo `prod.runs`.
- Las credenciales `Apollo API` y `HubSpot` (Header Auth) se crean a mano en
  n8n; los workflows las referencian por nombre.
- Si un nodo intermedio falla (p. ej. Open-Meteo caído), la ejecución de n8n
  queda en error pero **no** se hace PATCH de `error` a la API: el run queda
  en `running` hasta que alguien lo cierre. Mejora futura: un error-workflow
  de n8n que haga el PATCH con `estado: error`.
- Zona horaria de los schedules: `America/Mexico_City` (conservada).
