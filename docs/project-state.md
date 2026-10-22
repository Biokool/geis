# GEIS — Estado del proyecto (snapshot 2026-10-21)

## Madurez

**Operativo end-to-end.** La cadena completa del módulo Radar (01 scrapeo → 02 dedup+score+enriquecimiento → 03 señales → 04 CRM → 05 LinkedIn) está verificada en producción local con datos reales. GEIS base (análisis territorial, reportes, DENUE) funcional con seed determinista.

## Datos actuales

| Dato | Valor |
|---|---|
| `prod.leads` | 160 leads (158 con `temp_zona`/geom, 40 `enriquecido_apollo`, 160 sincronizados a HubSpot) |
| `stg.leads_raw` | 146 (100% procesados) |
| `prod.denue_establishments` | 40 activos |
| `prod.runs` | 20 corridas registradas (últimas OK: 7, 10, 11, 15, 18, 19, 20, 4, 5) |
| `prod.warm_signals` | procesadas (2 seed + 1 real de LinkedIn) |
| `prod.user_investigations` | 0 (página Historial legítimamente vacía) |
| HubSpot | 160/160 companies espejadas con props custom |

## Integraciones

| Integración | Estado |
|---|---|
| Apollo.io | Conectada (`healthy/logged_in`), provider enrichment=cloud/apollo |
| HubSpot | Conectada; 3 propiedades custom creadas; scope `crm.schemas.custom.write` activo |
| LinkedIn | Conectada (org 107784991, vanity `biokool`); scopes `r/w_organization_social` |
| Apify | Token OK (plan FREE) — alternativa cloud del scraper, no usada |
| Open-Meteo | Operativa (weather local, sin clave) |

## Infraestructura

- PostGIS **16-3.5** (volumen recreado el 2026-10-19 con backup previo).
- n8n **2.35.7** con 5 workflows importados con IDs estables y 3 credenciales operativas.
- Scraper Playwright 1.49.0 (imagen 2.1 GB), `/scrape` verificado.
- Frontend rebuild 3 veces; bundle actual `index-CsXbjQBn.js` (dashboard de Inicio).
- Limpieza de disco: ~24 GB recuperados (imágenes huérfanas + build cache).

## Últimos cambios de código

- Frontend: `Inicio.tsx` (dashboard KPI), `Mapa.tsx` (controles top-right, limit 100), `Leads.tsx`/`Kpis.tsx` (limit 100), `lib/api.ts` (`LeadCurado` + `enriquecido_apollo` + `crm_synced_at`).
- Workflows: `02-dedup-score.json` (3 Code nodes), `03-signal-catcher.json` (nodo Parsear JSON + rewire), `04-crm-sync.json` (Preparar payload), `05-linkedin-signals.json` (endpoints + robustez).
- Compose: `N8N_RESTRICT_FILE_ACCESS_TO`, `N8N_ENCRYPTION_KEY`, vars de nube en `api`.

## Salud

- Todos los contenedores `healthy`.
- `/pipelines/runs` 200 OK (fix `detalle` aplicado a 7 filas).
- Sin 404 de código actual (el `/api/runs/activos` era una pestaña con bundle viejo).

## Deuda y riesgos vivos

- Ver [backlog.md](backlog.md).
