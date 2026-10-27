# ADR-011 — Ingesta real del INEGI: DENUE masivo + Censo 2020 AGEB + Marco Geoestadístico

- **Estado:** Aceptada (2026-10-26)
- **Ámbito:** `backend/app/etl/jobs/{denue_bulk,censo_ageb,aggregates}.py`, `backend/.gitignore` (`backend/data/`), `backend/app/connectors/denue_api.py`, `.env` (`DENUE_API_TOKEN`), datos en `prod.denue_establishments` / `prod.inegi_agebs` / `prod.agg_ageb_scian` (excepción acotada a AGENTS.md: el owner autorizó esta ingesta)
- **Relacionadas:** ADR-012 (Overpass), ADR-013 (catálogo SCIAN y NSE), SRS §5.2–5.6, §7.3; `sessions/2026-10-26.md`

## Contexto

La app solo tenía **datos demo**: 40 establecimientos DENUE y 4 AGEB ficticias de
la Condesa (edición `DENUE_SEED_2026`). `marco_entidades`/`marco_municipios`
estaban vacíos y `agg_ageb_scian`, también. El objetivo acordado fue llenar el
reporte real de Querétaro (punto 20.611976, −100.420430) con **datos oficiales
del INEGI**, incorporando CDMX (09) como segunda entidad para comparar.

Hallazgos del descubrimiento (importantes para futuras ingestas):

- El conector `denue_api.py` apuntaba a `/buscar?lat&lon&radio&token`, forma que
  **nunca existió**: el API v1 del DENUE usa rutas con segmentos
  (`/buscar/{cond}/{lat},{lon}/{radio}/{token}`, `/ficha/{id}/{token}`,
  `/BuscarEntidad/{cond}/{entidad}/{inicio}/{fin}/{token}`; radio ≤ 5000 m).
- El token real estaba en `.env` como `DENUE_TOKEN`; `config.py` lee
  **`DENUE_API_TOKEN`** → el conector corría en modo stub aunque hubiera token.
- `www.inegi.org.mx` bloquea `webfetch` con captcha Radware, pero las URLs
  `contenidos/` funcionan por HTTPS directo. Una URL inexistente devuelve
  **HTTP 200 con HTML de "Página no encontrada"**: siempre validar magic bytes.
- DENUE masivo (`denue_<ent>_shp.zip`) trae **solo shapefile** (DBF/SHP/SHX/PRJ
  + diccionario + metadatos), sin CSV: hay que leer el DBF con `pyshp`.
- El Censo 2020 por AGEB urbana trae CSV (230 columnas, UTF-8 con BOM) y el
  Marco Geoestadístico trae la capa `<ent>a.shp` en **LCC EPSG:6362**.

## Decisión

1. **Fuentes y alcance:** paquetes oficiales por entidad, descargados a
   `backend/data/raw/` (271 MB, **gitignored**):
   - `censo_<ent>.zip` — `ageb_mza_urbana_<ent>_cpv2020_csv.zip`
     (AGEB + manzana; tercera edición, 2021-07-26).
   - `mg_<ent>.zip` — cartografía `889463807469/<ent>_<slug>.zip` (AGEB urbana
     `<ent>a.shp` + entidad/municipio/locales).
   - `denue_<ent>.zip` — `denue_<ent>_shp.zip` (edición 20/05/2026).
2. **DENUE (`denue_bulk.py`):** DBF leído con `pyshp` en `latin-1`; validación
   (nombre, SCIAN de 6 dígitos, lat/lon dentro de México, dedupe por id+entidad)
   y **cuarentena contada**, no silenciosa. Carga por lotes de 2 000 en las
   particiones `denue_est_p<ent>`; idempotencia por **(edición, cve_ent)**
   (DELETE + INSERT dentro de una sola transacción). `per_ocu` → `estrato_ordinal`
   1–7 por el primer entero del texto; `cve_ageb` se compone
   `ent+mun+loc(4)+ageb(4)` = 13 caracteres (igual que `inegi_agebs.cvegeo`).
3. **Censo (`censo_ageb.py`):** solo filas de **AGEB urbana** (`MZA == "000"` y
   `AGEB != "0000"`); se cruzan por `CVEGEO` con `<ent>a.shp`, reproyectado
   LCC→WGS84 con `pyproj` + `shapely` (validación de rango de México con el
   centroide de una muestra). Se ingieren **solo AGEB urbanas** (las rurales
   `<ent>ar` y las manzanas quedan para fase 2). Ediciones separadas por entidad
   (`CPV2020_AGEB_09`, `CPV2020_AGEB_22`) para idempotencia y linaje claros.
4. **Agregados (`aggregates.py`):** se añadió `JOIN prod.inegi_agebs` al
   recalcular `agg_ageb_scian`: la tabla tiene FK a `inegi_agebs.cvegeo` y el
   ~3 % de establecimientos sin AGEB urbana la hacían fallar.
5. **Retiro del seed:** se borraron las 40 filas DENUE y 4 AGEB de
   `DENUE_SEED_2026` (y su edición) para no duplicar CDMX con datos ficticios.
6. **Conector del API:** rutas corregidas a la forma real (token en la ruta),
   radio acotado a 5 000 m, caché/backoff intactos, y el **stub imita las 22
   claves reales** (`Id`, `Nombre`, `Clase_actividad`, `Estrato`, `Latitud`…).
   El token quedó en `DENUE_API_TOKEN` (36 caracteres); `DENUE_TOKEN` se eliminó.
7. **Operación:** el código está montado en vivo, pero **uvicorn no recarga**:
   tras cambiar conectores hay que `docker compose restart api`; tras cambiar
   `.env`, `docker compose up -d api` (recrea; `restart` no re-lee env).

## Consecuencias

- ✅ **571 316 establecimientos** DENUE válidos (CDMX 462 520 + Qro 108 796;
  284 en cuarentena de 571 600 leídos) y **3 320 AGEB** (2 431 CDMX con 9 138 524
  hab; 889 Qro con 1 873 781 hab) contra totales oficiales urbanos coherentes.
  **234 846** filas de `agg_ageb_scian`.
- ✅ Cobertura del cruce DENUE→AGEB: **99.7 % CDMX / 97.0 % Qro** (el resto son
  AGEB rurales o sin AGEB, fuera del alcance urbano de esta ingesta).
- ✅ El reporte real ya usa censo observado (129 069 hab a 2 km; 85.7 % Internet,
  58.1 % auto, 62.6 % PC, 35 835 viviendas) en lugar del fallback determinista.
- ⚠️ 2 AGEB por entidad del Censo no tienen polígono en el MG 2020
  (`2200100390061`, `2201800470088`, `0901101101107`, `0901201351227`):
  quedaron fuera y se registraron en `records_quarantine`.
- ⚠️ El ISM se dispara en zonas de baja competencia (p. ej. 1 competidor en 2 km
  de SCIAN 531112 → ISM miles): es el comportamiento de la fórmula `D/(O+1)`,
  no un bug de datos; el veredicto lo interpreta como océano azul.
- ⚠️ El DENUE del API no expone el **código** SCIAN (solo `Clase_actividad`):
  para análisis por clase se sigue usando el bulk, no el API.
- 🧪 8 tests nuevos (`tests/test_etl_inegi.py`): mapeos del DENUE, bandas NSE,
  invariantes del catálogo, forma del stub, rutas reales y fallback de espejos
  Overpass. **147/147**.
