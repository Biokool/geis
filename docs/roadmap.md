# GEIS — Roadmap

## Objetivo general

Plataforma de geomarketing + prospección B2B self-hosted que cualquier PYME mexicana pueda operar local-first con espejos en la nube a voluntad.

## Fases

| Fase | Estado | Progreso |
|---|---|---|
| 0. Infraestructura local (Docker, PostGIS, API, web) | **Hecha** | 100% |
| 1. Módulo Radar E2E (scrapeo→CRM→LinkedIn) | **Hecha** | 100% |
| 2. Endurecimiento (docs, git, observabilidad) | **En curso** | 80% |
| 3. Operación continua (email, automatización de campañas) | Pendiente | 0% |
| 4. Escala (multi-tenant, despliegue expuesto) | Pendiente | 0% |

### Detalle fase 2 (en curso)

- [x] Documentación técnica completa (PKM: docs/, ADRs, changelog, sesiones).
- [x] Repositorio git inicial con todo el trabajo versionado.
- [ ] Remoto git (GitHub privado) — pendiente de decisión del owner.
- [ ] Monitoreo/alertas (hoy: `docker compose ps` + bitácora manual).

### Fase 3 — Operación continua (ideas)

- Email provider (hoy deliberadamente apagado; nunca con dominio corporativo sin calentar).
- Automatización de cadencias SDR (n8n) sobre leads con `etapa=nuevo`.
- Refresh incremental DENUE con `DENUE_API_TOKEN`.
- Re-OAuth LinkedIn documentado con expiry alert (`expires_at` ya guardado).

### Fase 4 — Escala

- Auth real de API para multiusuario/exposición.
- Publicación del dist (Docker Hub / GHCR) para instalar sin clonar.
- Panel de costos Apollo/Apify (créditos consumidos por run).

## Bloqueos

- Ninguno técnico. La decisión pendiente es de producto (remote git, email sending).

## Riesgos

| Riesgo | Prob. | Impacto | Nota |
|---|---|---|---|
| Token LinkedIn expira sin re-OAuth | Media | Medio | `expires_at` en provider; runbook existe |
| Agotamiento de créditos Apollo | Media | Bajo | Rama cloud simplemente no enriquece |
| Límite 1,000 contactos HubSpot (free) | Baja | Bajo | 160/1000 usados; limpiar espejos viejos |
| Rotación accidental de `N8N_ENCRYPTION_KEY` | Baja | Alto | Documentado en security/conventions |
