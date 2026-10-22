# GEIS — Visión general

## Qué es

**GEIS (GeoEnterprise Intelligence System)** es una plataforma open source de geomarketing para México que unifica datos oficiales del INEGI (DENUE, Censo de Población y Vivienda, Marco Geoestadístico) sobre **PostgreSQL + PostGIS** para:

1. **Evaluar ubicaciones comerciales** con modelos espaciales (ISM, Huff, TAM, IDT) y producir reportes de viabilidad con veredicto.
2. **Generar leads B2B con scoring** que combina señal espacial (GEIS) y conductual (módulo Radar).
3. **Ejecutar el ciclo comercial completo**: scrapeo → deduplicado → scoring → señales → CRM → LinkedIn, orquestado por n8n.

## Tesis del ecosistema

- **GEIS es la capa de inteligencia**: ¿*dónde* están las oportunidades? (datos oficiales, modelos espaciales, veredictos).
- **El módulo Radar es la capa de ejecución**: ¿*cómo* las capturo? (scrapeo, scoring conductual, señales, pipeline comercial, CRM).
- No compiten: **se ensamblan** sobre la misma infraestructura (PostGIS + FastAPI + React + Docker Compose local-first). Una sola tabla de leads (`prod.leads` con `source` denue/gmaps/manual/linkedin), un solo score (espacial + conductual), un solo mapa, un solo dashboard, una sola API.

## Componentes

| Componente | Rol |
|---|---|
| `db` | PostgreSQL 16 + PostGIS 3.5; esquemas `prod` / `stg` / `quarantine` |
| `api` | FastAPI (backend); expone `/api/v1/*`, aplica migraciones Alembic, gobierna providers y runs |
| `web` | SPA React 18 (Vite + TypeScript + Tailwind + shadcn/Radix + ECharts + Leaflet) servida por Nginx |
| `n8n` | Orquestador de los 5 workflows del módulo Radar (`radar-01..05`) |
| `scraper` | Microservicio Python + Playwright/Chromium: scrapeo de Google Maps → `stg.leads_raw` |
| `redis` | Caché de API y rate limiting |
| `cloudflared` | Túnel rápido público hacia el frontend (perfil `tunnel`, opcional) |

## Principios de diseño

- **Local-first / anti-cautiverio**: los datos aterrizan primero en Postgres; la nube (Apollo, HubSpot, LinkedIn) es espejo. Cada capacidad externa es un *provider* conmutable (`local` / `cloud` / `disabled`) desde la página **Sistema**, sin reescribir pipelines.
- **Regla de oro**: si la nube falla, el pipeline usa el modo local o salta la rama; nunca se pierde la corrida.
- **Bloqueo por orden**: el backend rechaza (`409`) un paso del pipeline si el anterior no terminó OK.
- **Sin secretos en código**: todo vive en `.env` (no se commitea); `.env.example` solo trae plantillas.

## Documentación relacionada

- Arquitectura detallada: [architecture.md](architecture.md)
- Inventario completo: [inventory.md](inventory.md)
- Historial de cambios: [changelog.md](changelog.md)
- Estado actual: [project-state.md](project-state.md) · [working-memory/current-state.md](working-memory/current-state.md)
- Docs conceptuales previas: [ECOSISTEMA-FUSION.md](ECOSISTEMA-FUSION.md), [MODULO-CONFIGURACION-IA.md](MODULO-CONFIGURACION-IA.md), [REVISION-FINAL.md](REVISION-FINAL.md)
