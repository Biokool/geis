# ADR-003: Convención de retorno de Code nodes y parsing robusto de archivos en workflows n8n

- **Fecha:** 2026-10-20
- **Estado:** Accepted
- **Autor:** Claude Code (sesión opencode, GLM)
- **Origen:** Claude Code

## Contexto

Tras la primera ejecución real de la cadena Radar surgieron dos clases de falla sistemáticas en los workflows: errores `"A 'json' property isn't an object [item 0]"` en Code nodes y `"Unexpected token '~'"` al leer archivos JSON.

## Problema

1. Los Code nodes (JS) de `02-dedup-score.json` y `04-crm-sync.json` devolvían objetos planos/arrays crudos en modo `runOnceForEachItem`; n8n exige envolver cada item como `{ json: {...} }`.
2. El nodo "Leer signals/input.json" de `03-signal-catcher.json` entregaba el binario crudo; el Code node posterior hacía `JSON.parse` sobre un texto con **BOM** de Windows (`EF BB BF` → token `~`/`﻿`), rompiendo el paso 03.

## Alternativas consideradas

1. **String.prototype.trimStart + strip manual del BOM** en el Code node — frágil, reimplementa lo que n8n ya trae.
2. **Nodo `extractFromFile` (operación `fromJson`)** — parseo nativo de n8n tolerante al encoding, devuelve items ya parseados.
3. **Cambiar el formato de entrada a NDJSON** — mover el problema al proveedor de las señales.

## Decisión

- **Regla para Code nodes**: en modo `runOnceForEachItem` el retorno es siempre `{ json: {...} }`; en `runOnceForAllItems` puede ser un array de items. Corregidos: "Score y línea", "Extraer dominio", "Merge Apollo" (02) y "Preparar payload" (04).
- **Paso 03**: insertar nodo **"Parsear JSON"** (`n8n-nodes-base.extractFromFile`, `operation: fromJson`, `binaryPropertyName: data`) entre la lectura del archivo y la lógica; "Parsear señales" reescrito para consumir `$input.first().json.data`; conexiones re-cableadas. El BOM deja de ser responsabilidad del workflow.
- Los workflows mantienen **modo `runOnceForAllItems`** donde el retorno de arrays SÍ es correcto (verificado en 03: "Parsear señales", "Consolidar", "Armar warm" — no se tocaron).

## Justificación

Usar el nodo nativo elimina una clase entera de bugs de encoding (BOM/CRLF) en lugar de parchear caso por caso; la convención de envoltura `{json:...}` es el contrato interno de n8n y evita el fallo en runtime con items.

## Consecuencias

- La cadena 01→05 completa ejecuta en verde (runs 15, 17–20).
- Nueva convención documentada (conventions.md) para cualquier workflow futuro.
- Señales generadas por herramientas Windows ya no requieren pre-procesamiento manual.

## Impacto

- Archivos: `n8n/workflows/02-dedup-score.json`, `03-signal-catcher.json`, `04-crm-sync.json`.
- Regresión: ninguna; re-import upsert por ID (ADR-002).

## Referencias

- [ADR-002](ADR-002-endurecimiento-n8n.md) · [environment.md](../environment.md) (codificación) · [architecture.md](../architecture.md) (flujo del paso 03)
