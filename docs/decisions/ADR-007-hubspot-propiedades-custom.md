# ADR-007: Espejo HubSpot — propiedades custom `biokool_*` y sincronización por lotes

- **Fecha:** 2026-10-20
- **Estado:** Accepted
- **Autor:** Claude Code (sesión opencode, GLM)
- **Origen:** Claude Code

## Contexto

radar-04 espeja los leads curados a HubSpot (provider `crm` en modo cloud) para que el equipo comercial opere el pipeline también fuera de GEIS. El sync mapea etapa/score/línea a propiedades de Company.

## Problema

Primera corrida OK con **0 leads sincronizados**: HubSpot respondía **400 `PROPERTY_DOESNT_EXIST`** para `biokool_etapa`, `biokool_score` y `biokool_linea`. Además, la app privada no tenía permiso para crear esquemas.

## Alternativas consideradas

1. **Mapear a propiedades estándar de HubSpot** (`lifecycle_stage` etc.) — contamina la semántica estándar del CRM del cliente, pierde el namespace del vertical y se pelea con configuraciones existentes.
2. **Guardar solo score como nota** — degrada el espejo: el CRM pierde filtrabilidad por etapa/línea.
3. **Crear 3 propiedades custom de Company vía API** — namespaced, filtrables, espejo 1:1 del pipeline.

## Decisión

1. El owner añadió el scope **`crm.schemas.custom.write`** a la app privada de HubSpot (único paso manual).
2. Las 3 propiedades se crearon **programáticamente** vía `POST https://api.hubapi.com/crm/v3/properties/companies` (una por propiedad, documentado en deployment.md).
3. radar-04 sincroniza **en lotes de 100 por corrida** (respeto al rate limit): la segunda corrida completó los 160/160 leads.

## Justificación

El namespace `biokool_*` hace explícito que esas propiedades las escribe GEIS (facilita limpieza/auditoría y evita colisiones), y crearlas por API las vuelve reproducibles para cualquier cuenta HubSpot nueva — coherente con el aprovisionamiento programático de ADR-002.

## Consecuencias

- 160/160 companies espejadas con etapa/score/línea actualizables por cada corrida de radar-04.
- **Dependencia operativa**: si alguien borra las propiedades en HubSpot, el sync vuelve a fallar con `PROPERTY_DOESNT_EXIST` — recrearlas con el runbook lo resuelve.
- Tope del plan free de HubSpot: 1,000 contactos (160 usados); limpiar espejos obsoletos al rotar verticales.

## Impacto

- Externo: schema de Companies en la cuenta HubSpot (3 propiedades custom).
- Interno: `04-crm-sync.json` (fix "Preparar payload", ADR-003), provider `crm` cloud/hubspot habilitado.

## Referencias

- [deployment.md](../deployment.md) (sección HubSpot) · [ADR-003](ADR-003-code-nodes-n8n.md) · [project-state.md](../project-state.md)
