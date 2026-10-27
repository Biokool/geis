# ADR-012 — Overpass con espejos en cascada y timeout de 45 s

- **Estado:** Aceptada (2026-10-26)
- **Ámbito:** `backend/app/connectors/overpass.py`
- **Relacionadas:** ADR-011 (ingesta), `reports/context.py` (`movimiento_acceso.vialidades`), `sessions/2026-10-26.md`

## Contexto

El reporte real de Querétaro salió con `movimiento_acceso.vialidades = []`
justo cuando la pestaña «Movimiento» debía mostrar vías. El conector original
tenía un **único endpoint** (`overpass-api.de`) y `TIMEOUT_S = 15`; la consulta
`way[highway~trunk|primary|secondary](around:2000…)` tarda ~37–40 s en frío en
el contenedor (cola del intérprete), así que siempre caía por timeout y devolvía
`[]` en silencio (honesto, pero inútil).

Pruebas desde el contenedor (2026-10-26, CDMX y Qro):

| Espejo | Resultado |
|---|---|
| `overpass-api.de` | 200 con **158 ways** (CDMX, 45 s) y 558 (Qro, 2 km, ~38 s) |
| `overpass.kumi.systems` | timeout a 20–45 s en todas las pruebas |
| `overpass.private.coffee` | timeout a 20–45 s |
| `overpass.osm.ch` | **200 pero datos incompletos**: 0 ways en el centro de CDMX |

(El fallo de TLS que se veía con `curl` desde Windows era del stack schannel del
host; `httpx` dentro del contenedor sí negocia correctamente.)

## Decisión

1. **Espejos en cascada:** `OVERPASS_MIRRORS = (overpass-api.de, kumi.systems,
   private.coffee)`; se intenta en orden y se usa la primera respuesta 200 con
   JSON. `overpass.osm.ch` se **descarta** (responde 200 con dataset incompleto:
   peor que un error, porque parece éxito).
2. **Timeouts:** `TIMEOUT_S = 45` por espejo (cold start real) y
   `[timeout:20]` dentro de la consulta QL.
3. **Degradación honesta:** si los tres espejos fallan se devuelve `[]` y se
   registra un `warning` por espejo; nunca se inventan vialidades ni se bloquea
   el reporte.
4. **Contrato intacto:** `fetch_vialidades(lat, lon, radio_m=2000, limite=12)`
   sigue siendo función de módulo (mockeable en tests, ver `test_seccion1.py`).

## Consecuencias

- ✅ El reporte regenerado (`b576bed8…`, mismo link público) trae **12
  vialidades**, la primera **Avenida 5 de Febrero a 48.6 m**, coherente con el
  corredor industrial del punto.
- ✅ Degradación: si el primario está saturado se usa un espejo; el peor caso
  (todos caídos) cuesta 3 × 45 s antes de devolver `[]`.
- ⚠️ La generación de reportes subió a ~82 s en frío (Overpass domina); es
  aceptable para un proceso asíncrono, pero cualquier uso interactivo futuro
  debería cachear por bbox.
- 🧪 2 tests nuevos: fallback al segundo espejo y `[]` si todos fallan.
