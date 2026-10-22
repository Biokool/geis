# Working Memory — estado actual

> Última actualización: 2026-10-21, fin de sesión 3. Este archivo es la primera parada al retomar el proyecto; se refresca cada sesión (el histórico vive en sessions/ y changelog.md).

## Objetivo activo

Módulo Radar **operativo y verificado E2E**. Documentación PKM completada. **Repositorio git fundado (solo local).** Siguiente: verificación visual del usuario y decisión sobre remoto.

## Entorno

- Windows (PowerShell 5.1) · Docker Engine 29.7.2 · Compose v5.4.0 · Git 2.43.0.windows.1
- PostGIS `16-3.5` · n8n `2.35.7` (puerto 5678) · 7 servicios saludables
- Git identity: GERAS / chino.mauries@gmail.com · **Sin remoto configurado**

## Reglas inviolables

- No tocar `backend/app` ni `frontend/src` sin autorización (excepciones activas registradas: ADR-004).
- `N8N_ENCRYPTION_KEY`: no rotar jamás sin re-importar credenciales.
- JSON para n8n/PowerShell: UTF-8 sin BOM.
- `prod.runs.detalle`: siempre dict (ADR-005). Bitácora append-only (marcar error, no borrar).
- Workflows: editar JSON en disco → re-importar (upsert por ID). CLI dentro del contenedor: `-e N8N_RUNNERS_BROKER_PORT=5680`.

## Datos actuales

- `prod.leads`: **160** (158 con `temp_zona`/geom, 40 `enriquecido_apollo`, 160 `crm_synced_at` espejados a HubSpot).
- Última cadena completa en verde: runs 7 (01), 20 (02), 15 (03), 18/19 (04), 4/5 (05).
- LinkedIn conectado (org 107784991, vanity `biokool`); Apollo healthy; provider `crm`=cloud/hubspot, `enrichment`=cloud/apollo.

## Hecho y verificado (no repetir)

- Cadena 01→05 completa, gating 409 verificado, `/pipelines/runs` 200 OK, APIs desde host OK, dashboard frontend deployado (bundle `index-CsXbjQBn.js`).
- ADR-001..007 escritos; changelog exhaustivo; runbooks en deployment.md (LinkedIn OAuth manual, propiedades HubSpot, marcado de runs).

## En progreso / pendiente inmediato

1. **Verificación visual del usuario** del dashboard tras hard refresh (Ctrl+F5) — único chequeo abierto.
2. **Remoto git** — el repo es local-only; el owner decide (GitHub privado sugerido).
3. Backlog P1: alerta expiración token LinkedIn, endpoint de conteo (dashboard itera cursores), `make radar`.

## Comandos de arranque rápido

```powershell
docker compose ps                                   # salud
Invoke-RestMethod http://localhost:3000/api/v1/system/health
Invoke-RestMethod "http://localhost:3000/api/v1/pipelines/runs?limit=5"   # bitácora
docker compose up --build -d web                    # tras cambiar frontend (+ hard refresh)
```

## Mapa de conocimiento

- Cómo funciona: `docs/overview.md` → `architecture.md` → `api/rest.md`
- Cómo operar: `deployment.md` (runbooks) · `installation.md`
- Por qué es así: `docs/decisions/` (ADR-001..007)
- Historial: `changelog.md` · `ai-history.md` · `sessions/`
- Estado y planes: `project-state.md` · `roadmap.md` · `backlog.md`
