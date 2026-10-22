# GEIS — Historial de asistencia IA (ai-history)

> Registro de las sesiones donde una IA (Claude Code / opencode CLI, modelo GLM de z-ai) ejecutó trabajo real sobre este repositorio. El detalle día por día vive en [sessions/](sessions/) y el inventario de cambios en [changelog.md](changelog.md).

## Sesión 1 — 2026-10-19 · Arranque e infraestructura

- **Alcance:** bring-up completo del stack, scraper Playwright, upgrade PostGIS 16-3.5, endurecimiento de n8n (encryption key, credenciales por CLI, IDs estables), validación de credenciales Apollo/Apify, limpieza de ~24 GB.
- **Decisiones IA-emitidas:** ADR-001 (PostGIS), ADR-002 (n8n programático).
- **Aprendizajes de la sesión:** los archivos JSON nacidos en Windows deben validarse contra BOM antes de importarlos a n8n; la importación de workflows es por archivo en Windows (no directorio); la encryption key de n8n es de un solo uso vitalicio.

## Sesión 2 — 2026-10-20 · Integraciones y cadena E2E

- **Alcance:** LinkedIn OAuth manual + radar-05; fixes a Code nodes (`{json:...}`) y al parsing de archivos (nodo `extractFromFile`); `N8N_RESTRICT_FILE_ACCESS_TO`; propiedades custom HubSpot; ejecución completa 01→05 con 160 leads y 160 espejos CRM.
- **Decisiones IA-emitidas:** ADR-003 (Code nodes + parsing), ADR-006 (LinkedIn), ADR-007 (HubSpot).
- **Aprendizajes:** el Task Broker de n8n 2.x colisiona al ejecutar CLI contra un contenedor en marcha (`-e N8N_RUNNERS_BROKER_PORT=5680` lo resuelve); el Postgres node v2.6 exige `ssl:"disable"` como string; HubSpot falla silenciosamente con 400 `PROPERTY_DOESNT_EXIST` si faltan las propiedades custom — pero la corrida se marca OK, hay que leer el `detalle`.

## Sesión 3 — 2026-10-21 · Verificación, frontend y PKM

- **Alcance:** auditoría de datos/APIs desde host; fix `prod.runs.detalle` (500→200); excepción autorizada para frontend (límites ≤100, `ZoomControl`, dashboard KPI en Inicio, `LeadCurado` extendido); 2 rebuilds de `geis-web`; diagnóstico del 404 fantasma (`/api/runs/activos` = pestaña con bundle viejo); documentación PKM completa; **git init + commit fundacional**.
- **Decisiones IA-emitidas:** ADR-004 (frontend), ADR-005 (detalle dict).
- **Aprendizajes:** las pestañas abiertas con bundles obsoletos generan 404 que parecen bugs del backend — hard refresh tras cada rebuild; el 500 de un endpoint puede ser dato inválido, no código; contar leads sin `total` exige iterar `next_cursor` (hasta 5 rondas de 100 en el dashboard).

## Convenciones que la IA debe respetar (leer antes de operar)

1. **AGENTS.md manda:** no tocar `backend/app` ni `frontend/src` sin autorización explícita del owner (las excepciones se registran — ver ADR-004).
2. **UTF-8 sin BOM** para todo JSON tocado por n8n o PowerShell.
3. **Los workflows se editan en disco** (`n8n/workflows/*.json`) y se re-importan (upsert por ID), nunca solo en la UI.
4. **Bitácora append-only:** los runs no se borran; se marcan `error` con nota.
5. Al terminar una sesión: actualizar [working-memory/current-state.md](working-memory/current-state.md), dejar sesión del día en [sessions/](sessions/), y registrar cambios en [changelog.md](changelog.md).
