# GEIS — Backlog

Prioridad: **P0** = próximo sprint · **P1** = planificado · **P2** = backlog frío · **P3** = idea.

## P0

- [ ] **Configurar remoto git** (GitHub privado del owner) y pushear el repo. Hoy solo existe el repo local con el commit inicial.
- [ ] **Verificación de usuario en browser** tras el rebuild del dashboard: hard refresh y recorrer Inicio/Mapa/Kpis/Leads/LeadsRadar/Operación (el único chequeo pendiente de la sesión).

## P1

- [ ] Alerta de expiración del token LinkedIn (leer `expires_at` del provider y avisar N días antes en Sistema).
- [x] Contador total de leads sin iterar cursor — ✅ 2026-10-21 (Revisión Profunda): `GET /api/v1/leads/count` con filtros etapa/línea/source; badge del menú y KPIs lo usan.
- [ ] Toast/UI cuando `/leads*` devuelve 422 por límite (defensa en profundidad si alguien reintroduce `limit>100`).
- [ ] `make radar` — target de Makefile que dispare la cadena 01→05 en orden con verificación de gating.
- [ ] Documentar proceso de creación exacta de las 3 propiedades custom de HubSpot (payload completo por propiedad) en deployment.md.

## P2

- [ ] Suite de tests para los workflows n8n (hoy verificación manual CLI + SQL).
- [ ] E2E del frontend (Playwright) para las páginas del Radar.
- [ ] Auth de la API (JWT ya firmado con SECRET_KEY; falta guard en rutas) para despliegue expuesto.
- [ ] Export Excel (`formato=excel` responde 501; CSV funciona con tope 5,000).
- [ ] `GET /api/v1/reports/{id}/pdf` (fase 2 del backend, tooltips honestos en UI).
- [ ] `POST /api/v1/leads/sync` (fase 2; el `DELETE /investigations/{id}` ya está implementado).
- [ ] Panel de costo de créditos Apollo/Apify por run.
- [ ] Limpieza de registros `detalle` anómalos en el origen (hoy el ADR-005 normaliza existentes; los writers ya respetan dict).

## P3

- [ ] Modo multi-tenant (varias empresas en la misma instalación).
- [ ] Publishing de imágenes Docker pre-construidas.
- [ ] Conector Twenty CRM como alternativa HubSpot (provider crm ya soporta `provider` conmutable).
- [ ] Scraper cloud vía Apify para elugar el Playwright local (2.1 GB de imagen).

## Tech debt registrado

- `frontend/src` y `backend/app` modificados bajo excepción autorizada (ver changelog 2026-10-20/21): la próxima modulación del dashboard debería considerar extraer el hook de paginación por cursor a `lib/` para reuso.
- Los runs marcados `error` con nota "marcado manual" (runs 2,3,6,8,9,16) viven en `prod.runs` como historia — no limpiar (append-only).
