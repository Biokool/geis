# Working Memory — estado actual

> Última actualización: 2026-10-26, cierre de la validación funcional E2E (+ fix ADR-010 del 500 en Analizar). Este archivo es la primera parada al retomar el proyecto; se refresca cada sesión (el histórico vive en `sessions/` y `changelog.md`).

## Objetivo activo

Validación funcional E2E completada (15 GETs, CRUDs, cadena 01→05 con scrape real de Querétaro, filtros geo operativos, fix del 500 en Analizar con giro libre). Siguiente: **verificación visual del owner** en navegador (Ctrl+F5) y **commit + push** del working tree (2 secciones + fixes de esta sesión).

## Entorno

- Windows (PowerShell 5.1) · Docker Engine 29.7.2 · Compose v5.4.0 · Git 2.43.0.windows.1
- PostGIS `16-3.5` · n8n `2.35.7` (puerto 5678) · 6 contenedores arriba (`db`, `redis`, `api`, `web`, `n8n`, `scraper`)
- Git identity: GERAS / chino.mauries@gmail.com · remoto `origin` = <https://github.com/Biokool/geis.git> (working tree commiteado y empujado el 2026-10-26: 2 secciones + ADR-008/009/010 + fixes de cadena)
- BD en revisión Alembic **0006 (head)**
- `geis-api` monta `./docs:/docs:ro` y `./n8n:/n8n:ro` (fix 2026-10-26; antes `FileNotFoundError` de docs en tests)

## Reglas inviolables

- No tocar `backend/app` ni `frontend/src` sin autorización (excepciones registradas: ADR-004, ADR-008, ADR-009 del fallback geo y ADR-010 del 500 en reports).
- `N8N_ENCRYPTION_KEY`: no rotar jamás sin re-importar credenciales. `N8N_API_KEY` no existe (sin REST API de n8n).
- JSON para n8n/PowerShell: UTF-8 sin BOM; cuerpos con acentos → **bytes UTF-8** (`curl.exe --data-binary @archivo`; `-d "..."` mangling comillas → 422 falso).
- `prod.runs.detalle`: siempre dict (ADR-005). Bitácora append-only (marcar error con motivo, no borrar).
- Workflows: editar JSON en disco → `n8n import:workflow` (desactiva) → `n8n publish:workflow --id=<id>` (no soporta `--all`; `update:workflow` deprecado) → **reiniciar n8n**. CLI: `-e N8N_RUNNERS_BROKER_PORT=5680`.
- Geocoding: si nada resuelve → **422**; nunca un punto por defecto. Movilidad: siempre `estimado: true`.
- n8n: un nodo con 0 items de entrada **se salta** y la cadena muere sin callback (usar guardas `skip` o `alwaysOutputData`).
- SQL crudo: `knowledge_facts`/`company_profiles`/`ai_usage_log` viven en `public` (migración 0003, compatibilidad SQLite) — **no** calificarlas con `prod.`; y todo `except` que traga un error SQL va con `safe_rollback(db)` (ADR-010) o envenena la sesión.

## Datos actuales

- `prod.leads`: **178** (160 CDMX seed + 18 scrape real de Querétaro del run 24 + manuales de señales warm). `enrich-geo` 2026-10-26 con fallback de dirección (ADR-009): `actualizados=158`, `pendientes=176` (solo falta `scian`, que no sale del texto).
- Filtros geo con datos reales: `entidad=Querétaro` → 82; `+municipio=Santiago de Querétaro` → 75; `+colonia=Centro` → 17; `cp=76000` → 18. `geo-filters` en cascada poblado.
- `prod.denue_establishments`: 40 activos (solo 3 SCIAN, zona Condesa CDMX) → AGEB 4 filas; `marco_entidades`/`marco_municipios` 0 filas (ETL censal sigue en backlog).
- `prod.reports`: 1 real («Prueba integración 2 secciones», Roma Norte) + reporte de validación `53c27e9f` (2026-10-25) + 2 de validación ADR-010 (2026-10-26, giro libre → 201).
- Runs en verde: 24 (01 Qro), 25 (02), 29/30 (03), 28 (04), 26 (05); 27 (03) marcado error con motivo.

## Hecho y verificado (no repetir)

- **139/139 tests** (`docker compose exec api pytest -q`); 15 GETs 200; CRUD reports/investigations/proposals/share/export verificados contra la BD real.
- **POST /reports con giro de texto libre validado E2E (ADR-010):** 201 `AVANZAR` + auto-aprendizaje en `public.knowledge_facts` + 2.º POST 201 + GET 200 (antes: 500 por `prod.knowledge_facts` + sesión envenenada).
- **b2b-prospecting y lookalike** validados con datos reales (200, scores y ranking).
- **Webhooks n8n:** `webhookId` UUID en los 5 nodos; `POST /webhook/radar-0X` → 200. Cron 02 corregido. IDs de workflow en `public.workflow_entity` (01 `czWM…`, 02 `-mWN…`, 03 `DLIv…`, 04 `e8sg…`, 05 `y3Kc…`).
- **Radar-03 rama warm arreglada y probada con señal real:** `POST /signals` → run 30 ok, señal `procesada`, lead manual +25.
- **E2E scrape real:** run 24 radar-01 con target Querétaro Centro 76000, giros bodegas → 18 leads geo-parseados.
- 422 legítimos (no bugs): `{}` en reports/signals; compare sin `scian`/`giro` por ítem; geocode sin resolución.

## En progreso / pendiente inmediato

1. **Verificación visual del owner** (Ctrl+F5): Leads con filtros geo Qro, Mapa `?modo=radar`, Operación sin scrape (target por entidad/municipio/zona), Panel Radar.
2. Backlog §5: ETL censal completo (AGEB/Marco INEGI) — mientras tanto el fallback de dirección cubre entidad/municipio/colonia/CP; Overpass 502 → reintentos; LinkedIn parcial; sin `/config`; chunk 2.19 MB.
3. `scian` de leads: solo DENUE cercano (≤500 m) — con 40 establecimientos casi todos quedan sin SCIAN; crecer DENUE o mapear giro→SCIAN si el owner lo pide.

## Comandos de arranque rápido

```powershell
docker compose ps
docker compose exec api alembic current                    # debe decir 0006 (head)
docker compose exec api pytest -q                           # 139 expected
Invoke-RestMethod http://localhost:3000/api/v1/system/health
Invoke-RestMethod http://localhost:3000/api/v1/leads/count
Invoke-RestMethod "http://localhost:3000/api/v1/leads/count?entidad=Quer%C3%A9taro"   # 82
# re-llenar geo tras scrape nuevo (idempotente):
curl.exe -s -X POST http://localhost:3000/api/v1/leads/enrich-geo -H "Content-Type: application/json" --data-binary "@$env:TEMP\enrich.json"
# tras cambiar el frontend:
docker compose build web; docker compose up -d web       # + Ctrl+F5 en el navegador
# tras cambiar el backend (montado en vivo):
docker compose restart api
```

## Mapa de conocimiento

- Cómo funciona: `overview.md` → `architecture.md` → `api/rest.md` → `ARQUITECTURA-2-SECCIONES.md`
- Cómo operar: `GUIA-DE-INICIO.md` (usuario) · `deployment.md` (runbooks) · `installation.md`
- Qué existe y dónde: `INVENTARIO-SABUESO.md` (53) · `INVENTARIO-RADAR.md` (102 + R1–R17) · `REVISION-2-SECCIONES.md`
- Por qué es así: `docs/decisions/` (ADR-001..010)
- Historial: `changelog.md` · `ai-history.md` · `sessions/`
- Estado y planes: `project-state.md` · `roadmap.md` · `backlog.md`
