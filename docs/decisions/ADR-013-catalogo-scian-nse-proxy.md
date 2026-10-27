# ADR-013 — Catálogo SCIAN curado (top-200 + alias) y proxy NSE del Censo 2020

- **Estado:** Aceptada (2026-10-26)
- **Ámbito:** `backend/app/data/catalogo_scian.py` (nuevo), `backend/app/etl/jobs/catalogo_scian.py` (nuevo), `backend/app/etl/jobs/censo_ageb.py` (NSE), tablas `prod.cat_scian` / `prod.cat_giro_scian` / `prod.inegi_agebs` (excepción acotada a AGENTS.md: autorizada por el owner)
- **Relacionadas:** ADR-011 (datos que alimentan el catálogo), SRS §3.2/§3.4/§3.9, `sessions/2026-10-26.md`

## Contexto

1. `prod.cat_scian` tenía **10 clases semilla** y `cat_giro_scian`, unos pocos
   alias. Cualquier giro de texto libre que no matcheara caía en `722515`
   (cafeterías) y cualquier SCIAN desconocido se analizaba con parámetros
   neutros (atractivo 0.7, λ 2.0) — el denominador común de los avisos de
   «catálogo semilla».
2. Los leads scrapeados quedan sin `scian` cuando el DENUE cercano es escaso
   (antes: 40 filas demo); con 571 316 establecimientos ya es viable mapear
   giro→clase.
3. El Censo 2020 permite estimar NSE por AGEB con variables de bienes, pero
   **no existe `P_25A29`** en el conjunto AGEB (los grupos son `P_15A17`,
   `P_18A24`, `POB15_64`, `P_60YMAS`, `POB65_MAS`).

## Decisión

### Catálogo SCIAN

1. **Selección data-driven:** el job toma las **200 clases más frecuentes** del
   DENUE cargado (cubre >95 % de los establecimientos de 09+22) y añade las
   clases referenciadas por alias aunque no estén en el top (p. ej. `622111`,
   hospitales). `cat_scian` quedó en **205 clases** (incluye las 4 semilla sin
   datos en 09/22: petroquímica, acero, telas, autotransporte).
2. **Parámetros por sector + excepciones:** `SECTOR_PARAMS` define
   `(thermal, attr, λ)` para los 23 sectores SCIAN y `OVERRIDES` ajusta ~60
   clases relevantes (supermercados, restaurantes por tipo, escuelas,
   universidades, hoteles, talleres, lavanderías…). Semántica:
   - `thermal_intensity` = propensión a requerir climatización/refrigeración
     (calor del proceso); manofactura de alimentos ~0.8–0.9, retail ~0.2–0.4.
   - `base_attractiveness` = fuerza como ancla de Huff: supermercados 0.95,
     universidades/hospitales 0.85, conveniencia 0.5–0.6.
   - `lambda_default` = decaimiento por distancia: conveniencia 2.5–3.0,
     anclas regionales 1.2–1.5.
3. **Alias curados:** **529 etiquetas** para **193 clases** (`ALIASES`), en
   minúsculas y con variantes reales («taquería», «tacos», «tortas»;
   «estética», «salón de belleza», «barbería»; «cajero/contador»…). Confianza
   1.0 para etiquetas canónicas y 0.75–0.95 para genéricas o de mayoreo
   («abarrotes» vs «mayoreo de abarrotes»), porque `resolver_scian` usa
   `ILIKE '%giro%' ORDER BY confidence DESC`.
4. **Upsert idempotente:** `ON CONFLICT` en `cat_scian` (actualiza descripción y
   parámetros) y en `cat_giro_scian (giro_label, scian_code)`. Si una clase con
   alias no existe en el DENUE cargado, se omite el alias con warning (nunca se
   inventa la descripción).

### Proxy NSE

5. **Fórmula:** score 0–1 = promedio ponderado de la cobertura de bienes
   (`VPH_INTER` 35 %, `VPH_PC` 25 %, `VPH_AUTOM` 25 %, `VPH_CEL` 15 %),
   denominador `VIVPARH_CV`, pesos renormalizados si falta un dato.
   Bandas: **Alto ≥ 0.80**, Medio a medio alto ≥ 0.60, Medio ≥ 0.45,
   Medio bajo ≥ 0.30, Bajo < 0.30 (etiqueta simplificada, **no** es el índice
   AMAI oficial).
6. **Grupo 25–29 (estimado):** `R = POB15_64 − P_15A17 − P_18A24 −
   (P_60YMAS − POB65_MAS)`; se reparte `round(R·5/35)` a 25–29 (supuesto
   uniforme dentro de 25–59) y el resto a 30–59. Queda documentado en
   `data_editions.notes` y es reproducible.
7. `pob_sin_clasificar = max(0, POBTOT − POB0_14 − POB15_64 − POB65_MAS)`
   (guardia ante descuadres del CSV), y `prom_ocupantes_viv` acotado a 99.99
   por el `Numeric(4,2)`.

## Consecuencias

- ✅ Distribución NSE plausible y distinta por ciudad (AGEB): CDMX 1 187 «Medio a
  medio alto», 675 «Medio», 485 «Alto», 45 «Medio bajo», 5 «Bajo»; Qro 303 «Medio
  a medio alto», 228 «Alto», 223 «Medio», 101 «Medio bajo», 19 «Bajo» (34 y 15
  sin datos suficientes para calcular el score).
- ✅ `resolver_scian` ya encuentra giros comunes («abarrotes»→461110,
  «gimnasio»→713943, «lavandería»→812210, «veterinaria»→541941) y el reporte de
  naves industriales resuelve `531112` sin aviso de catálogo semilla.
- ✅ Refresco reproducible con un comando (`catalogo_scian --top 200`); sin
  datos nuevos no cambia nada.
- ⚠️ Los parámetros son **heurísticos por sector**, no una calibración
  empírica: se documentan como tales y viven en un solo módulo editable.
- ⚠️ El proxy NSE usa bienes del hogar (no ingreso); es comparable entre AGEB,
  no contra la distribución AMAI oficial. El 25–29 es una estimación declarada.
- ⚠️ Las clases fuera del top-200 y sin alias usan parámetros neutros y se
  avisan en `advertencias` (comportamiento previo, sin cambios).
