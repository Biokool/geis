# ADR-012 — Overpass en paralelo, con presupuesto, caché y timeout de nginx

- **Estado:** Aceptada (2026-10-26; actualizada el mismo día tras el 504 de «Reporte»)
- **Ámbito:** `backend/app/connectors/overpass.py`, `frontend/nginx.conf`
- **Relacionadas:** ADR-011 (ingesta), `reports/context.py` (`movimiento_acceso.vialidades`), `sessions/2026-10-26.md`

## Contexto

El reporte real de Querétaro salió con `movimiento_acceso.vialidades = []`
justo cuando la pestaña «Movimiento» debía mostrar vías. El conector original
tenía un **único endpoint** (`overpass-api.de`) y `TIMEOUT_S = 15`; la consulta
`way[highway~trunk|primary|secondary](around:2000…)` tarda ~30–40 s en frío en
el contenedor (cola del intérprete), así que siempre caía por timeout y devolvía
`[]` en silencio (honesto, pero inútil).

Pruebas desde el contenedor (2026-10-26, CDMX y Qro):

| Espejo | Resultado |
|---|---|
| `overpass-api.de` | 200 con **158 ways** (CDMX, 45 s) y 558 (Qro, 2 km, ~38 s); también 200 con 48 ways en 32 s |
| `overpass.kumi.systems` | timeout a 20–45 s en todas las pruebas |
| `overpass.private.coffee` | timeout a 20–45 s |
| `overpass.osm.ch` | **200 pero datos incompletos**: 0 ways en el centro de CDMX |
| `overpass.osm.jp` | `ConnectError` (0.8 s) |

El fallo de TLS que se veía con `curl` desde Windows era del stack schannel del
host; `httpx` dentro del contenedor sí negocia correctamente.

**Incidente (mismo día):** la pestaña «Reporte» devolvía **504**. Causa doble:
(1) el reporte tardaba ~140 s porque, con el primario saturado, se probaban
3 espejos **en secuencia** (45 s cada uno) y (2) nginx cortaba a los **60 s**
(`proxy_read_timeout` por defecto). El backend terminaba el reporte (201 en
`8000`) pero el navegador ya había recibido el 504.

## Decisión

1. **Consulta por unión, no regex:** tres `way["highway"="…"]` unidos dentro de
   `(...)`; es más rápida que `way[highway~"^(trunk|primary|secondary)$"]` y
   mantiene el mismo resultado.
2. **Espejos en paralelo:** `OVERPASS_MIRRORS = (overpass-api.de, kumi.systems,
   private.coffee)` se consultan **a la vez** (`ThreadPoolExecutor`) y se usa la
   primera respuesta 200 con JSON. `overpass.osm.ch` se **descarta** (responde
   200 con dataset incompleto: peor que un error, porque parece éxito).
3. **Presupuesto:** `TIMEOUT_S = 50` por espejo y `PRESUPUESTO_TOTAL_S = 55` de
   espera al primero que responda; la consulta QL declara `[timeout:25]`.
4. **Caché en proceso:** 6 h por bbox (`lat/lon` a 4 decimales, radio, límite) y
   10 min para un fallo, para que repetir el reporte del mismo punto no vuelva
   a esperar a Overpass.
5. **Degradación honesta:** si todos fallan se devuelve `[]` y se registra un
   `warning`; nunca se inventan vialidades ni se bloquea el reporte.
6. **Timeout del proxy:** en `frontend/nginx.conf`, `/api/` usa
   `proxy_read_timeout` y `proxy_send_timeout` de **300 s** (y
   `proxy_connect_timeout` 10 s). El 504 ya no puede ocurrir por un reporte
   lento.
7. **Contrato intacto:** `fetch_vialidades(lat, lon, radio_m=2000, limite=12)`
   sigue siendo función de módulo (mockeable en tests).

## Consecuencias

- ✅ El reporte regenerado (`b576bed8…`, link público intacto) trae **12
  vialidades**, la primera **Avenida 5 de Febrero a 48.6 m**, coherente con el
  corredor industrial del punto.
- ✅ Verificado el 2026-10-26 en el punto del 504 (Villas del Sol, Qro):
  `fetch_vialidades` = **33.8 s / 12 vías**, segunda llamada **0.00 s** (caché);
  `POST /reports` vía nginx = **79–82 s → 201 AVANZAR**, sin 504.
- ✅ Degradación: un solo espejo caído ya no cuesta 45 s extra; el peor caso
  (todos caídos) es ~55 s y el fallo se recuerda 10 min.
- ⚠️ La generación de reportes sigue en ~45 s de cálculo propio (PostGIS +
  Huff + censo) además de Overpass; es aceptable para un proceso síncrono, pero
  si se quiere respuesta inmediata habría que hacerla asíncrona.
- 🧪 3 tests nuevos: fallback con espejos en paralelo, `[]` si todos fallan
  (con caché negativa) y caché de una consulta exitosa.
