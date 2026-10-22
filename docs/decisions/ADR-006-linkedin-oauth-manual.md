# ADR-006: Integración LinkedIn — OAuth manual con token en `.env` y provider configurable

- **Fecha:** 2026-10-20
- **Estado:** Accepted
- **Autor:** Claude Code (sesión opencode, GLM)
- **Origen:** Claude Code

## Contexto

radar-05 debe leer estadísticas de la página corporativa de LinkedIn (Biokool, org `107784991`, vanity `biokool`) para detectar picos de engagement y generar señales cálidas. Requiere la **Community Management API** con scopes `r_organization_social` y `w_organization_social`.

## Problema

El flujo OAuth de LinkedIn redirige al callback del backend (`:8000`), pero en la instalación local el puerto corresponde al contenedor `geis-api`; el navegador del usuario no puede completar el redirect sin maniobras. Además, el workflow 05 tenía endpoints inconsistentes con la API real de LinkedIn.

## Alternativas consideradas

1. **Esperar a implementar refresco automático de token** — sobreingeniería para un token de ~60 días con uso semanal.
2. **Túnel público para el callback** — abrir superficie de red para un flujo que corre dos veces al año.
3. **OAuth manual guiado + token persistido en `.env` + provider configurable** — transparente, auditable, cero código nuevo permanente.

## Decisión

1. **Flujo manual documentado** (runbook en deployment.md): detener `geis-api` si el callback corre fuera de Docker → autorizar en el navegador → copiar `code` del redirect → canjear por `access_token` (POST directo a `linkedin.com/oauth/v2/accessToken`) → volcar en `.env` como `LINKEDIN_ACCESS_TOKEN` → recrear la api.
2. **Descubrimiento de `org_id`** vía API (Biokool = `107784991`) y configuración del provider por `PUT /api/v1/providers/linkedin` con `access_token`, `org_id`, `vanity_name` y `expires_at` (alerta de expiración pendiente en backlog).
3. **Fixes al workflow 05** (`05-linkedin-signals.json`): endpoints correctos de la Community Management API + robustez (validación de respuesta, tolerancia a picos nulos); re-import por ID.
4. `geis-web` se reinició para limpiar la caché DNS de Nginx tras los cambios de red internos.

## Justificación

La regla de oro del ecosistema: los datos aterrizan en Postgres y la nube es espejo. Un token con expiración conocida y refresco manual semestral no justifica infraestructura de OAuth propia; el costo real (una ventana manual cada ~60 días) queda capturado en `expires_at`.

## Consecuencias

- radar-05 ejecuta end-to-end (runs 4, 5 OK): escribe `prod.linkedin_stats`, genera 1 señal cálida real y marca `prod.runs` 'ok'.
- El token vive en `.env` y en la config del provider (mismo nivel de secreto, dos copias documentadas).
- Re-OAuth = repetir el runbook; sin él, radar-05 fallará por 401 (visible en bitácora, no rompe la cadena: 05 no tiene gating sobre otros pasos ni otros dependen de él).

## Impacto

- Archivos: `.env`, `05-linkedin-signals.json`, provider `linkedin` en `prod.providers`.
- Verificado: `GET /api/v1/integrations/linkedin/status` → `connected=true` con scopes correctos.

## Referencias

- [deployment.md](../deployment.md) (runbook completo) · [ADR-002](ADR-002-endurecimiento-n8n.md) · [security.md](../security.md)
