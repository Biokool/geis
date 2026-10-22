# ADR-005: Gobernanza de `prod.runs.detalle` — contrato dict estricto

- **Fecha:** 2026-10-21
- **Estado:** Accepted
- **Autor:** Claude Code (sesión opencode, GLM)
- **Origen:** Claude Code

## Contexto

`GET /api/v1/pipelines/runs` explotaba con **500 Internal Server Error**. Causa: el modelo Pydantic `RunOut` declara `detalle: dict`, pero 7 filas de `prod.runs` contenían **arrays JSON** (p. ej. `["texto"]`) o **NULL** — producto de updates manuales y de writers provisionales durante las pruebas de la cadena.

## Problema

Una sola fila inválida tumba el endpoint completo de bitácora → la página Operación queda inutilizable y no se puede auditar el pipeline.

## Alternativas consideradas

1. **Relajar el modelo** (`detalle: dict | list | None`) — convierte un bug de writers en contrato perpetuo; el frontend tendría que manejar 3 formas.
2. **Filtrar filas inválidas en el endpoint** — oculta el problema y miente en la bitácora.
3. **Normalizar los datos + fijar el contrato dict** — el modelo ya tenía la forma correcta; el problema era el dato.

## Decisión

1. **Migración de datos puntual** (documentada, no repetible): arrays → `jsonb_build_object('error', <texto>)`; NULL → `{}`. 7 filas actualizadas.
2. **Contrato permanente**: `prod.runs.detalle` es SIEMPRE un objeto JSONB (`dict`), nunca array ni NULL. Vale para todo writer: workflows n8n, backend, SQL manual.
3. Los writers de workflows ya producen dict (nodos "Armar summary" etc.); los updates manuales de bitácora usan el patrón del runbook (`jsonb_build_object('error','marcado manual: ...')`).

## Justificación

`detalle` es un registro abierto de evidencia por corrida (conteos, errores, ids); un dict es la única forma que evoluciona sin romper consumidores. Validar en el borde (Pydantic) y normalizar el dato es la combinación correcta: el 500 era el sistema avisando, no un bug del endpoint.

## Consecuencias

- `/pipelines/runs?limit=100` → 200 OK con 20 corridas; página Operación funcional.
- Cualquier 500 futuro en este endpoint se investiga primero como dato inválido en `detalle`.
- Los runs históricos marcados "error" con nota manual se conservan (bitácora append-only).

## Impacto

- Contenido: `prod.runs` (7 filas, una sola vez).
- Código: ninguno (el modelo `RunOut` ya era correcto).
- Se referencia desde conventions.md, deployment.md, api/rest.md, installation.md.

## Referencias

- [ADR-004](ADR-004-frontend-radar-paginacion-dashboard.md) · [deployment.md](../deployment.md) (patrón SQL de marcado manual) · [api/rest.md](../api/rest.md)
