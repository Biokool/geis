# ADR-004: Frontend del Radar — excepción autorizada, paginación ≤100 y dashboard KPI

- **Fecha:** 2026-10-21
- **Estado:** Accepted
- **Autor:** Claude Code (sesión opencode, GLM)
- **Origen:** Claude Code (bajo autorización explícita del owner)

## Contexto

`AGENTS.md` declara `backend/app` y `frontend/src` territorio de workers: no tocar. Pero la operación real del Radar reveló tres problemas de integración que viven en el frontend, y solo el owner puede autorizar la excepción.

## Problema

1. Las páginas pedían `limit=500/1000` a `/leads*`; el backend responde **422** (`Query(le=100)`) → Mapa/Leads/Kpis sin datos.
2. Los endpoints no devuelven `total` (paginación por cursor) → las UI no podían contar ni paginar completo.
3. La página Inicio era un placeholder; el usuario necesitaba un tablero general de KPIs (leads, etapas, enriquecimiento, CRM) de un vistazo.

## Alternativas consideradas

1. **Subir el límite del backend a 1000** — cambia el contrato de API y castiga memoria/latencia; el tope existe por diseño.
2. **Endpoint agregado de conteo** — correcto a futuro (está en backlog), pero bloqueante para desbloquear la operación.
3. **Frontend pagina por cursor (≤100 por ronda) + dashboard con conteo iterado** — respeta el contrato, funciona hoy, sin tocar backend.

## Decisión

**Excepción autorizada por el owner** (documentada aquí y en conventions.md). Cambios:

- `Mapa.tsx`: `limit` 500→100; `ZoomControl` a `topright` (evita encimar los controles de Geoman) con `zoomControl={false}` en el `MapContainer`.
- `Leads.tsx` y `Kpis.tsx`: `limit` 1000→100.
- `lib/api.ts`: `LeadCurado` extendido con `enriquecido_apollo?: boolean` y `crm_synced_at?: string | null` (espejo del modelo Pydantic).
- `Inicio.tsx` reescrito como **dashboard KPI general**: itera `next_cursor` en rondas de 100 para conteos exactos, KPIs de etapas/score/enriquecimiento/CRM + feed de runs.

## Justificación

El contrato de paginación por cursor es la decisión de diseño del backend (memory-safety con datasets crecientes); adaptar los clientes es más barato y correcto que relajar el servidor. La excepción se acota a los archivos listados y queda registrada para auditabilidad.

## Consecuencias

- Regla permanente: **todo cliente de `/leads*` pide ≤100 y sigue `next_cursor`**; nunca asumir `total`.
- El conteo del dashboard hace hasta N rondas de 100 → si los leads crecen a miles, activar el endpoint de conteo del backlog.
- Tras cada rebuild de `geis-web` hay que hacer hard refresh: las pestañas con bundle viejo pollean endpoints inexistentes (caso `/api/runs/activos` 404).

## Impacto

- Archivos: `frontend/src/pages/{Inicio,Mapa,Leads,Kpis}.tsx`, `frontend/src/lib/api.ts`.
- Verificación: `tsc && vite build` verde; bundles servidos `index-BosjGVjM.js` y `index-CsXbjQBn.js` comprobados desde el host.

## Referencias

- [ADR-005](ADR-005-gobernanza-prod-runs-detalle.md) (el dashboard también consume `/pipelines/runs`) · [api/rest.md](../api/rest.md) · [conventions.md](../conventions.md)
