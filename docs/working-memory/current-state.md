# Working Memory — estado actual

> Última actualización: 2026-10-26, cierre de la ingesta real del INEGI (DENUE 2026-05 + Censo 2020 AGEB urbana para CDMX y Querétaro, ADR-011/012/013) sobre la validación E2E previa. Este archivo es la primera parada al retomar el proyecto; se refresca cada sesión (el histórico vive en `sessions/` y `changelog.md`).

## Objetivo activo

Datos oficiales cargados y reporte real regenerado con el **mismo link público** (`/r/<token>`, share id 3 → report `b576bed8-c2ff-40bd-8e45-8ecc5ae141ed`). Siguiente: **commit + push** del working tree (ETL INEGI, catálogo SCIAN, conectores, tests, ADR-011/012/013, docs) y **verificación visual del owner** del reporte regenerado.

## Entorno

- Windows (PowerShell 5.1) · Docker Engine 29.7.2 · Compose v5.4.0 · Git 2.43.0.windows.1
- PostGIS `16-3.5` · n8n `2.35.7` (puerto 5678) · 6 contenedores arriba (`db`, `redis`, `api`, `web`, `n8n`, `scraper`)
- Git identity: GERAS / chino.mauries@gmail.com · remoto `origin` = <https://github.com/Biokool/geis.git> (último push 2026-10-26: 2 secciones + ADR-008/009/010 + fixes de cadena; **pendiente** push de la ingesta INEGI)
- BD en revisión Alembic **0006 (head)**
- `geis-api` monta `./docs:/docs:ro` y `./n8n:/n8n:ro` (fix 2026-10-26; antes `FileNotFoundError` de docs en tests)
- Datos crudos INEGI en `backend/data/raw/` (**271 MB, gitignored**): `denue_{09,22}.zip`, `censo_{09,22}.zip`, `mg_{09,22}.zip`
- Token DENUE en `.env` como **`DENUE_API_TOKEN`** (36 caracteres); para cambios de env usar `docker compose up -d api` (restart no relee)

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
- `prod.denue_establishments`: **571 316** de `DENUE_2026_05` (CDMX 462 520 · Qro 108 796; 284 en cuarentena; 931/840 clases SCIAN distintas). Cobertura AGEB 99.7 % CDMX / 97.0 % Qro. Seed demo retirado (0 filas).
- `prod.inegi_agebs`: **3 320** AGEB urbanas (CDMX 2 431 → 9 138 524 hab; Qro 889 → 1 873 781 hab; 2 sin polígono por entidad en cuarentena). `prod.agg_ageb_scian`: **234 846** filas. `marco_entidades`/`marco_municipios` siguen en 0 (fase 2).
- `prod.cat_scian`: **205 clases**; `prod.cat_giro_scian`: **529 alias** para 193 clases (`catalogo_scian --top 200`).
- `prod.reports`: reporte real regenerado `b576bed8-c2ff-40bd-8e45-8ecc5ae141ed` (AVANZAR, 82 s; 129 069 hab a 2 km, Internet 85.7 %, 12 vialidades; cita `DENUE_2026_05` + `CPV2020_AGEB_22`) + los de validación previos. Share id 3 repuntado al nuevo (misma URL `/r/<token>`, expira 2026-11-25).
- Runs en verde: 24 (01 Qro), 25 (02), 29/30 (03), 28 (04), 26 (05); 27 (03) marcado error con motivo.

## Hecho y verificado (no repetir)

- **147/147 tests** (`docker compose exec api pytest -q`, 8 nuevos de INEGI/Overpass); 15 GETs 200; CRUD reports/investigations/proposals/share/export verificados contra la BD real.
- **POST /reports con giro de texto libre validado E2E (ADR-010):** 201 `AVANZAR` + auto-aprendizaje en `public.knowledge_facts` + 2.º POST 201 + GET 200 (antes: 500 por `prod.knowledge_facts` + sesión envenenada).
- **b2b-prospecting y lookalike** validados con datos reales (200, scores y ranking).
- **Webhooks n8n:** `webhookId` UUID en los 5 nodos; `POST /webhook/radar-0X` → 200. Cron 02 corregido. IDs de workflow en `public.workflow_entity` (01 `czWM…`, 02 `-mWN…`, 03 `DLIv…`, 04 `e8sg…`, 05 `y3Kc…`).
- **Radar-03 rama warm arreglada y probada con señal real:** `POST /signals` → run 30 ok, señal `procesada`, lead manual +25.
- **E2E scrape real:** run 24 radar-01 con target Querétaro Centro 76000, giros bodegas → 18 leads geo-parseados.
- **Ingesta INEGI real (ADR-011):** DENUE masivo por entidad (DBF latin-1, `pyshp`, idempotencia por edición+entidad) y Censo 2020 AGEB urbana cruzado con `<ent>a.shp` LCC→WGS84; seed demo retirado. Totales cuadran con INEGI (9.14 M CDMX / 1.87 M Qro urbanos).
- **Catálogo SCIAN data-driven (ADR-013):** 205 clases / 529 alias; `resolver_scian` resuelve giros comunes («abarrotes»→461110, «gimnasio»→713943, «lavandería»→812210, «veterinaria»→541941); proxy NSE por bienes del hogar en 3 320 AGEB.
- **Conectores:** DENUE API con rutas reales y token `DENUE_API_TOKEN` (probado en vivo: 2 428 resultados cerca del centro de Qro y ficha OK); Overpass con espejos en cascada (12 vialidades reales, Av. 5 de Febrero 48.6 m).
- **Reporte real + share:** `b576bed8…` regenerado en 82 s (AVANZAR) con datos observados; `prod.report_shares` id 3 repuntado (misma URL pública, expira 2026-11-25).
- 422 legítimos (no bugs): `{}` en reports/signals; compare sin `scian`/`giro` por ítem; geocode sin resolución.

## En progreso / pendiente inmediato

1. **Commit + push** del working tree de la ingesta INEGI (ETL, catálogo, conectores, `backend/data/raw` fuera por gitignore, tests, ADR-011/012/013, docs PKM).
2. **Verificación visual del owner** del reporte regenerado (misma URL `/r/<token>`) y de Leads con filtros geo Qro; Ctrl+F5 en el navegador.
3. Fase 2 INEGI: **manzanas y AGEB rurales** (`<ent>ar`), `marco_entidades`/`marco_municipios`, y 2 AGEB sin polígono por entidad (en cuarentena).
4. `scian` de leads: ahora sale del DENUE real (571 k) cuando hay establecimiento a ≤500 m; el resto sigue sin mapear (decisión pendiente del owner).
5. ISM en zonas de baja competencia (1 competidor → miles): es `D/(O+1)`; decidir si el owner quiere un cap o una nota explícita en el reporte.

## Comandos de arranque rápido

```powershell
docker compose ps
docker compose exec api alembic current                    # debe decir 0006 (head)
docker compose exec api pytest -q                           # 147 expected
Invoke-RestMethod http://localhost:3000/api/v1/system/health
Invoke-RestMethod http://localhost:3000/api/v1/leads/count
Invoke-RestMethod "http://localhost:3000/api/v1/leads/count?entidad=Quer%C3%A9taro"   # 82
# ETL INEGI (idempotente; --force para recargar)
docker compose exec api python -m app.etl.jobs.denue_bulk --edition DENUE_2026_05 --entidades 09,22
docker compose exec api python -m app.etl.jobs.censo_ageb --edo 22 --edition CPV2020_AGEB_22
docker compose exec api python -m app.etl.jobs.censo_ageb --edo 09 --edition CPV2020_AGEB_09
docker compose exec api python -m app.etl.jobs.aggregates --edition DENUE_2026_05
docker compose exec api python -m app.etl.jobs.catalogo_scian --top 200
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
- Por qué es así: `docs/decisions/` (ADR-001..013)
- Historial: `changelog.md` · `ai-history.md` · `sessions/`
- Estado y planes: `project-state.md` · `roadmap.md` · `backlog.md`
