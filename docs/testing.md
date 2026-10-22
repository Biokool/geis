# GEIS — Testing

## Suite existente

- **Backend**: `make test` → `docker compose exec api pytest -q` (pytest ≥8 + pytest-asyncio). Cobertura del worker backend original (modelos espaciales, API, validaciones). No se ha extendido en estas sesiones.
- **Frontend**: `npm run build` ejecuta `tsc && vite build` — el typecheck de TypeScript es la barrera de verificación de cada cambio de frontend (usado en los 3 rebuilds de `geis-web`).
- **Validación de workflows**: cada JSON de `n8n/workflows/` se valida con parser JSON e import upsert antes de ejecutar.

## Pruebas de humo (smoke tests) ejecutadas en las integraciones

| Prueba | Método | Resultado |
|---|---|---|
| Scraper | `POST /scrape` con `max_results=2` | 2 resultados OK |
| Credencial Postgres GEIS | Workflow temporal leyendo `prod.providers` | OK (tras fix `ssl:"disable"`) |
| radar-04 sin dependencias | Ejecución directa | 409 correcto (gating funciona) |
| radar-05 end-to-end | CLI + verificación SQL | `prod.linkedin_stats`, `warm_signals` y `runs` OK |
| Cadena completa 01→05 | Runs 7→20 | 160 leads, 160 en HubSpot, señales procesadas |
| APIs desde host | `/leads`, `/leads/curados`, `/pipelines/runs` | 200 OK, `lat/lon` presentes |
| Frontend | `tsc` + bundle servido + verificación manual de páginas | OK (bundles `index-BosjGVjM.js`, `index-CsXbjQBn.js`) |

## Cómo probar manualmente (regresión mínima)

```powershell
# API sana
Invoke-RestMethod http://localhost:3000/api/v1/system/health
# Paginación respeta límites (≤100) y devuelve next_cursor
Invoke-RestMethod "http://localhost:3000/api/v1/leads/curados?limit=100"
# Bitácora de runs sin 500
Invoke-RestMethod "http://localhost:3000/api/v1/pipelines/runs?limit=20"
# Datos de mapa presentes
psql: SELECT count(*) FROM prod.leads WHERE geom IS NOT NULL;   -- 158
psql: SELECT count(*) FROM prod.denue_establishments WHERE activo; -- 40
```

En la web: Inicio (KPIs ≠ 0), Mapa (pins + leyenda sin encimar controles), Operación (bitácora), Leads/LeadsRadar (tablas con datos), Historial **vacío legítimo** (0 investigaciones guardadas).

## Gaps conocidos

- Sin tests automatizados de workflows n8n (se validan por ejecución CLI + SQL).
- Sin e2e del frontend (verificación manual tras cada rebuild).
- Sin CI/CD: todo se verifica localmente antes del commit.
