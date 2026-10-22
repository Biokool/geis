# ADR-002: Endurecimiento y aprovisionamiento programático de n8n

- **Fecha:** 2026-10-19/21 (iterado)
- **Estado:** Accepted
- **Autor:** Claude Code (sesión opencode, GLM)
- **Origen:** Claude Code

## Contexto

El módulo Radar se orquesta con n8n 2.35.7 en Docker. Los 5 workflows vivían como JSON en `n8n/workflows/` sin IDs estables ni referencias de credenciales resueltas; la primera importación falló con `EISDIR` (import de directorio en Windows) y `null value in column "id"`.

## Problema

Hacer reproducible el aprovisionamiento de n8n: importar workflows de forma idempotente, inyectar credenciales sin exponer secretos en la UI, cifrar credenciales de forma estable entre recreaciones del contenedor, y restringir el acceso a archivos del host.

## Alternativas consideradas

1. **Setup manual por UI** — rápido una vez, no reproducible, secreto expuesto en pantallazos.
2. **n8n API REST** — requiere activar API key y mapear endpoints; la CLI de import es más directa para bootstrap.
3. **CLI `n8n import:workflow` / `import:credentials` con archivos UTF-8 sin BOM** — reproducible, idempotente con IDs.

## Decisión

1. **`N8N_ENCRYPTION_KEY`** generada una vez (64 hex), persistida en `.env` y pasada al servicio en `docker-compose.yml`. Jamás rotar.
2. **IDs Nanoid** inyectados en el campo `id` top-level de cada workflow JSON → import por archivo = **upsert** (re-importar no duplica).
3. **3 credenciales** creadas con `n8n import:credentials` desde JSON temporales sin BOM: `Postgres GEIS` (host `db`, `ssl:"disable"` como **string** — el booleano `false` rompe Postgres node v2.6), `Apollo API`, `HubSpot`. Sus **IDs reales** se inyectaron en las 22 referencias de credenciales de los workflows.
4. **`N8N_RESTRICT_FILE_ACCESS_TO=/signals`** en el servicio: único path legible por nodos de archivo (el paso 03 lee `input.json` de ahí).
5. Ejecución CLI dentro del contenedor en marcha: `-e N8N_RUNNERS_BROKER_PORT=5680` para esquivar el conflicto de puerto del Task Broker.
6. Eliminadas las variables `N8N_BASIC_AUTH_USER/PASSWORD` (legado deprecado).

## Justificación

La vía CLI es idempotente y auditable; los IDs estables permiten tratar los JSON como código (versionados en git) y el volumen `n8n_data` como estado derivado. La restricción de archivos reduce la superficie de exfiltración.

## Consecuencias

- Re-construir n8n desde cero es un procedimiento documentado (installation.md), no un recuerdo tribal.
- Rotar la encryption key = re-importar todas las credenciales (documentado como prohibición por defecto).
- Todo JSON generado en Windows para n8n debe escribirse **UTF-8 sin BOM** (convención global del repo).

## Impacto

- Archivos: `docker-compose.yml`, `.env(.example)`, los 5 JSON de workflows, volumen `n8n_data`.
- Riesgo residual: token LinkedIn vive en la credencial n8n y en `.env` (dos copias, mismo nivel de secreto).

## Referencias

- [security.md](../security.md) · [conventions.md](../conventions.md) · [installation.md](../installation.md) · [ADR-003](ADR-003-code-nodes-n8n.md)
