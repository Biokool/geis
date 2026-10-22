# GEIS × Biokool Radar — Índice de documentación

> Punto de entrada único de la base de conocimiento del proyecto. Actualizado: 2026-10-21.
> Regla de mantenimiento: todo cambio estructural o decisión se refleja aquí y en [changelog.md](changelog.md).

## Para empezar
- **[overview.md](overview.md)** — qué es GEIS, la fusión con Biokool Radar y el alcance del módulo Radar.
- **[working-memory/current-state.md](working-memory/current-state.md)** — **retomar aquí** al volver al proyecto: estado, pendientes y comandos de arranque.
- `README.md` (raíz) — arranque rápido del stack.

## Núcleo técnico
- **[architecture.md](architecture.md)** — servicios, flujo de la cadena Radar, modelo de datos y contratos (paginación, detalle de runs).
- **[inventory.md](inventory.md)** — inventario de archivos y directorios con propósito.
- **[environment.md](environment.md)** — variables de `.env`/`.env.example` y su significado.
- **[dependencies.md](dependencies.md)** — dependencias externas: APIs, credenciales, versiones.
- **[api/rest.md](api/rest.md)** — referencia de la API REST (routers, límites, paginación por cursor).

## Operación
- **[installation.md](installation.md)** — instalación desde cero (migraciones, seed, verificación).
- **[deployment.md](deployment.md)** — runbooks: ejecutar la cadena, OAuth manual de LinkedIn, propiedades HubSpot, marcado de runs, rebuilds.
- **[testing.md](testing.md)** — suite de pruebas y verificaciones de humo usadas en la integración.
- **[security.md](security.md)** — secretos, superficie expuesta, permisos y scope mínimo.

## Reglas y estado
- **[conventions.md](conventions.md)** — reglas del repositorio (AGENTS.md, UTF-8 sin BOM, bitácora append-only, edición de workflows).
- **[glossary.md](glossary.md)** — vocabulario de dominio (lead, warm signal, curado, staging…).
- **[project-state.md](project-state.md)** — salud actual, riesgos y deuda técnica.
- **[roadmap.md](roadmap.md)** — dirección a futuro.
- **[backlog.md](backlog.md)** — pendientes priorizados (P1/P2/P3).

## Decisiones (ADRs)
Registro inmutable de decisiones — leer la relevante antes de cambiar nada:
1. **[ADR-001](decisions/ADR-001-postgis-16-35.md)** — upgrade a PostGIS 16-3.5 con volumen recreado.
2. **[ADR-002](decisions/ADR-002-endurecimiento-n8n.md)** — n8n reproducible: credenciales e IDs inyectados por CLI.
3. **[ADR-003](decisions/ADR-003-code-nodes-n8n.md)** — contrato `{json:...}` en Code nodes + parsing de archivos sin BOM.
4. **[ADR-004](decisions/ADR-004-frontend-radar-paginacion-dashboard.md)** — frontend del Radar: excepción autorizada, paginación ≤100 por cursor, dashboard KPI en Inicio.
5. **[ADR-005](decisions/ADR-005-gobernanza-prod-runs-detalle.md)** — `prod.runs.detalle` siempre dict.
6. **[ADR-006](decisions/ADR-006-linkedin-oauth-manual.md)** — LinkedIn con OAuth manual y provider configurable.
7. **[ADR-007](decisions/ADR-007-hubspot-propiedades-custom.md)** — espejo HubSpot con propiedades custom `biokool_*`.

## Historial
- **[changelog.md](changelog.md)** — cambios por fecha (reconstruido desde la bitácora de sesiones hasta hoy).
- **[ai-history.md](ai-history.md)** — sesiones de IA: alcance, aprendizajes y convenciones vigentes para asistentes.
- **[sessions/](sessions/)** — bitácora por día: [2026-10-21](sessions/2026-10-21.md).

## Documentos de diseño (pre-existentes)
- **[ECOSISTEMA-FUSION.md](ECOSISTEMA-FUSION.md)** — blueprint original de la fusión GEIS × Radar (19-oct-2026, estado: implementado).
- **[PERFIL-EMPRESA.md](PERFIL-EMPRESA.md)** — plantilla maestra que configura el vertical del ecosistema (la lee el sistema automáticamente).
- **[PERFIL-EMPRESA.ejemplo-gimnasios.md](PERFIL-EMPRESA.ejemplo-gimnasios.md)** — ejemplo lleno de referencia ("FitLife Gimnasios").
- **[MODULO-CONFIGURACION-IA.md](MODULO-CONFIGURACION-IA.md)** — diseño del wizard de configuración + operador IA interna (5 API keys).
- **[REVISION-FINAL.md](REVISION-FINAL.md)** — auditoría integral del 19-oct-2026 con veredictos de tests y build.

---
*Mantenimiento: al cerrar una sesión, actualizar working-memory, sessions/, changelog.md y este índice si hay archivos nuevos.*
