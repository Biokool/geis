# REVISIÓN — Restructuración en 2 secciones (validación y trazabilidad)

> **Rol:** worker independiente de Validación y Trazabilidad (2026-10-21).
> No se modificó código de aplicación: todo lo de este documento salió de
> comandos ejecutados y lecturas directas sobre `~/workspace/geis-github/`.
> Documentos normativos: `ARQUITECTURA-2-SECCIONES.md`,
> `INVENTARIO-SABUESO.md` (53 filas), `INVENTARIO-RADAR.md` (102 filas + R1–R17).
> Baseline previo: 97 tests. Reporte de los workers: 135 tests y build verde.
> **Veredicto general: el reporte de los workers es correcto en tests, build y
> contrato; el recorrido funcional pasa; la trazabilidad cierra con
> 117 ✅ · 31 ⚠️ · 7 📌 sobre 155 filas** (detalle y motivos abajo).

---

## 1. Resumen de la validación técnica (evidencia real)

### 1.1 Tests backend — ✅ 135/135

Comando: `cd backend && python3 -m pytest tests -q`

```text
135 passed, 1 warning in 3.82s
```

El warning es ajeno al proyecto (`StarletteDeprecationWarning` de
`fastapi.testclient`). Desglose por archivo (ejecutado archivo por archivo):

| Archivo | Tests |
|---|---|
| `tests/test_analytics.py` | 29 |
| `tests/test_company_ai.py` | 20 |
| `tests/test_correccion_profunda.py` | 9 |
| `tests/test_revision_final.py` | 20 |
| `tests/test_scoring_unificado.py` | 19 |
| `tests/test_seccion1.py` (nuevo) | 22 |
| `tests/test_seccion2.py` (nuevo) | 16 |
| **Total** | **135** |

Los 97 previos (29+20+9+20+19) siguen verdes y se suman 38 nuevos
(22 de Sección 1 + 16 de Sección 2). Sin fallos.

### 1.2 Build frontend — ✅ verde, TypeScript incluido

Comando: `cd frontend && npm run build` (el script es `tsc && vite build`):

```text
✓ 830 modules transformed.
dist/index.html                     1.23 kB │ gzip:   0.68 kB
dist/assets/index-D8kUQN-S.css     77.91 kB │ gzip:  20.42 kB
dist/assets/index-CMRcDoLy.js    2,191.63 kB │ gzip: 688.74 kB
✓ built in 12.94s
```

`npx tsc --noEmit` adicional: **sin errores** (exit 0). Única observación:
aviso de Vite de chunk > 500 kB (2.19 MB sin code-splitting); es un aviso de
rendimiento, no un error.

### 1.3 Contrato frontend ↔ API — ✅ 0 huérfanas, 0 métodos incorrectos

Método: extracción de todas las llamadas de `frontend/src/lib/api.ts` y
`frontend/src/lib/apiGeo.ts` (33 llamadas distintas método+ruta, con
`${...}` normalizado a `{}`) cruzadas contra el volcado OpenAPI real de la
app FastAPI (45 rutas, 43 bajo `/api/v1`).

- **Huérfanas: 0.** Toda llamada de `api.ts`/`apiGeo.ts` tiene ruta backend.
- **Métodos incorrectos: 0.** Incluidos los casos delicados: providers se
  actualiza con **PUT** `/providers/{name}` (así lo documenta `apiGeo.ts` y
  así existe en el backend), el share se revoca con
  **DELETE** `/reports/{report_id}/share/{token}` y la ganadora se marca con
  **PATCH** `/investigations/{id}`.
- Nota de lectura: `deleteInvestigation` concatena (`'/investigations/' + id`);
  normalizada es `DELETE /api/v1/investigaciones/{}` y **sí existe**.
- Chequeo extra (fuera del alcance estricto): las llamadas directas desde
  páginas (`/leads`, `/leads/curados`, `/leads/curados/{id}` PATCH,
  `/analysis/b2b-prospecting`, `/pipelines/run/{stage}`, `apiBlob
  /leads/export`, `/system/health`, `/investigations`) también resuelven
  todas contra rutas reales con el método correcto.

### 1.4 Recorrido funcional con fakes/TestClient (scripts propios en `/tmp`)

HTTP externo siempre mockeado; sesiones fake con el patrón de
`tests/test_correccion_profunda.py` reutilizado como infraestructura, con
aserciones propias de esta validación.

| # | Chequeo | Resultado | Evidencia observada |
|---|---|---|---|
| a | `POST /territories/geocode` con `https://www.google.com/maps/@19.4326,-99.1332,17z` | ✅ **PASA** | 200; `lat=19.4326`, `lon=-99.1332` exactos; `fuente="link_maps"`; `stub=false`; etiqueta por reverse «Roma Norte, Cuauhtémoc, Ciudad de México». No hay destino falso: una dirección irresoluble devuelve 422 (cubierto por la suite). |
| b | Reporte con las 14 secciones pobladas vía `POST /reports` | ✅ **PASA** (con una precisión) | 201. Payload con `cabecera.ubicacion` legible (no «lat, lon» crudo); `clientes_zona.poblacion_total=24000` y 4 segmentos; `hogares_familias.viviendas_habitadas=9800`; `entorno_comercial.total_negocios=9` con **9 categorías**; `competencia.lista` con 2 ítems «PARECE ACTIVO»; `atractores_trafico.items` no vacío; NSE «Medio a medio alto» con referencia AMAI 2024; `movimiento_acceso.movilidad.vehicular.estimado=true`; vialidades presentes; `poblacion_viviendas.detalle.grupos_edad["30_59"]=11000`; TAM presente; fuentes con INEGI Censo 2020 y DENUE; `datos_sector.ticket_promedio` presente; `negocios_ancla.items` no vacío; `delivery.aplica=true`. **Precisión:** `competencia.anillo_exterior` salió `0` en esta ruta porque la fake de análisis reporta conteo 2 en ambos anillos (2−2=0, aritmética correcta); llamando a `build_report_context` directo con anillos 2 y 5 el diferencial es **3**, como pide Sabueso. Sin Valhalla (mock vacío) el alcance se etiqueta `alcance_tipo="radios"` — honestidad intacta. |
| c | Filtros geográficos reducen la lista | ✅ **PASA** | Con 3 leads de prueba: `/leads/count` sin filtro `total=3` → con `entidad=Ciudad de México` `total=2`; `/leads/curados` 3 → 2 ítems con el mismo filtro. Cascada `/catalogs/geo-filters`: sin fijar, municipios = {Ecatepec de Morelos, Guadalajara, Toluca}; fijando `entidad=México` → {Ecatepec de Morelos, Toluca} (CP 4→3, SCIAN 3→2). Las colonias no bajaron (3→3) porque «Centro» existe en ambas entidades en los datos de prueba: es coincidencia de datos, no fallo de la cascada (la restricción por entidad+municipio está en el SQL). `POST /leads/enrich-geo` sobre la fake: `actualizados=2, pendientes=2, detalle={con_geometria:1, solo_cp:1, sin_datos:1}`. |
| d | Share público crear → leer sin auth → revocar → 404 | ✅ **PASA** | `POST /reports/{id}/share` → 201 con token y `url=/r/{token}`; `GET /reports/shared/{token}` **sin autenticación** → 200; `DELETE /reports/{id}/share/{token}` → 204; `GET` posterior → **404**; token inexistente → 404. |
| e | Cadena Alembic 0001→0006 íntegra | ✅ **PASA** | Revisión de `revision`/`down_revision` en los 6 archivos: 0001(None) → 0002(0001) → 0003(0002) → 0004(0003) → 0005(0004, leads geo) → 0006(0005, report_shares). Cadena lineal, sin ramas ni huecos. |

### 1.5 Muestreo del frontend (verificación directa, sin fiarse de reportes)

| Elemento pedido | Encontrado |
|---|---|
| Selector de secciones en `Sidebar.tsx` con `localStorage` clave `geis:seccion` | ✅ `components/layout/Sidebar.tsx`: `CLAVE_SECCION='geis:seccion'`, lectura al montar y escritura al cambiar de sección o de ruta. |
| Rutas `/analizar`, `/aprende`, `/panel-radar`, `/reporte/:id/imprimir`, `/r/:token` en `App.tsx` | ✅ Las cinco existen; las dos últimas viven **fuera** del `AppLayout` (vista imprimible y vista pública sin chrome), como debe ser. |
| `PanelRadar.tsx` con las 4 gráficas | ✅ Embudo de conversión (funnel), Leads por línea recomendada (dona), Distribución de score (barras) y Actividad · últimos 14 días (líneas), todas ECharts con datos de la API (`/leads/count` por línea, `/leads/curados`, `/pipelines/runs`, LinkedIn status). Más 4 KPI y 4 alertas. |
| Filtros geo en `Leads.tsx` | ✅ Hook `useGeoFiltros()` (cascada entidad→municipio→colonia→CP+SCIAN) aplicado a `/leads/curados` y `/leads/count`. |
| Botón enrich-geo en `Operacion.tsx` y en `Leads.tsx` | ✅ En ambos: «🌎 Enriquecer geografía» → `POST /leads/enrich-geo`, con mensaje de actualizados/pendientes. |
| `?modo=radar` en `Mapa.tsx` | ✅ `searchParams.get('modo')==='radar'` activa preset (capas de leads y temperatura, panel de filtros geo, título «Mapa Radar»). |
| Pin arrastrable en `Analizar.tsx` | ✅ `Marker draggable` en minimapa Leaflet; al soltar, re-geocodifica la etiqueta (reverse). |
| Botones WhatsApp / PDF / Link invitado en `Reporte.tsx` | ✅ WhatsApp (`wa.me` con resumen + link), «PDF / Imprimir» (navega a `/reporte/:id/imprimir`) y «Link invitado» (crear/copiar/revocar share, token persistido en `localStorage` por reporte). |

**Nada de lo muestreado faltó.** Las parcialidades están en el detalle
(ver trazabilidad), no en la existencia de las piezas.

### 1.6 Nota metodológica sobre los workflows n8n

Las filas de workflows (Radar #10–#15, #23–#70) se verificaron por
estructura de nodos de los JSON en `n8n/workflows/` (los 5 workflows están
completos, con los nodos del original más los nodos GEIS de registro de
corrida y, en la 02, el nodo HTTP opcional de `enrich-geo` tras el scoring)
y por inspección puntual del SQL/JS donde vive la regla: score base
(#25/R2), bonus por calor y línea (R4/R5), upsert +25 (R6), guardado Apollo
(R7) y detección de señales (R9). Los 5 JSON se importan con
`active: false` (estado normal al importar en n8n; hay que activarlos en la
UI). **Ningún workflow se ejecutó contra n8n/Postgres reales en esta
validación** (ver pendientes).

---

## 2. Trazabilidad completa — Inventario Sabueso (Sección 1 · Ubicaciones)

**Resumen: 42 ✅ · 8 ⚠️ · 3 📌** (de 53).

| # | Función | Dónde vive ahora | Estado |
|---|---|---|---|
| 1 | Giro en texto libre → actividad/SCIAN | `frontend/src/pages/Analizar.tsx` (autocompletado con catálogo + giros del perfil, campo «SCIAN (editable)» con nota) + `backend/app/api/v1/analysis.py::resolver_scian` + fichas `app/analytics/sector_data.py` | ✅ implementada |
| 2 | Dirección en texto libre geocodificada | `POST /territories/geocode` (`app/geo/geocoding.py`, Nominatim/OSM); irresoluble → 422, nunca punto falso | ✅ implementada |
| 3 | Link de Google Maps → punto | `parse_maps_link` (`@lat,lon`, `!3d/!4d`, `?q=`, `query=`) + resolución de links cortos; chequeo (a) de §1.4 | ✅ implementada |
| 4 | Confirmación visual del punto | `Analizar.tsx`: minimapa Leaflet con pin arrastrable y reverse al soltar, sin salir del flujo | ✅ implementada |
| 5 | Radios 1 km y 2 km | `ReportCreate.radios=[1000,2000]`, análisis por anillos (preexistente) | ✅ implementada |
| 6 | Cabecera con ubicación legible | `build_report_context` + reverse de Nominatim; payload `cabecera.ubicacion` = «Roma Norte, Cuauhtémoc, …» (chequeo b) | ✅ implementada |
| 7 | Botón WhatsApp en el reporte | `Reporte.tsx`: `https://wa.me/?text=` con veredicto + link | ✅ implementada |
| 8 | Botón Guardar PDF | `Reporte.tsx` → ruta `/reporte/:id/imprimir` (`ReportePrint.tsx`, CSS print / «Guardar como PDF» del navegador), según lo declarado en el documento rector §2.8: no hay endpoint PDF binario | ✅ implementada |
| 9 | Link compartible modo invitado | Migración `0006_report_shares` + `POST/GET/DELETE` de shares en `reports.py` + ruta pública `/r/:token` (`ReporteCompartido.tsx`); chequeo (d) completo | ✅ implementada |
| 10 | Perfil del cliente (editorial del giro) | `sector_data.py` (editorial por ficha) + `build_report_context` (con caché en `knowledge_facts`); payload `perfil_cliente.editorial` poblado (chequeo b) | ✅ implementada |
| 11 | Clientes y resultado de la zona (segmentos) | `build_report_context` agrega AGEB → `clientes_zona` (población total + 4 segmentos; chequeo b) | ✅ implementada |
| 12 | Advertencias de honestidad | Notas fijas del builder + `EstimadoBadge` en la UI (preexistente) | ✅ implementada |
| 13 | Datos de mercado del giro (ticket, hora pico, % delivery, top) | `app/analytics/sector_data.py` por ficha con fuente citada; payload `datos_sector` (chequeo b) | ✅ implementada |
| 14 | Hogares y familias | `build_report_context` (`viv_habitadas`, ocupantes, % internet/computadora/auto); chequeo b | ✅ implementada |
| 15 | Atractores de tráfico ordenados con link a Maps | `build_report_context` (DENUE por categorías, `ST_Distance`) → `atractores_trafico.items` con `url_maps` (chequeo b) | ✅ implementada |
| 16 | Competencia: conteo por anillos | `analysis.py::competencia_por_radio` → `competencia.por_anillo` con ISM (preexistente) | ✅ implementada |
| 17 | Competencia: lista + «PARECE ACTIVO» + diferencial 1–2 km | `build_report_context` → `competencia.lista` (nombre, distancia, estado) y `competencia.anillo_exterior` (diferencial verificado = 3 con anillos 2/5; ver precisión del chequeo b) | ✅ implementada |
| 18 | Mapa 1: ubicación y negocios cercanos numerados | `Reporte.tsx`: Leaflet embebido con marcadores numerados correlacionados con la lista de competencia y leyenda por anillo | ✅ implementada |
| 19 | Mapa 2: atractores por categoría (9) con filtros | `app/analytics/categorias.py` (9 categorías exactas del inventario) + mapa de atractores con chips en `Reporte.tsx` + capa en `Mapa.tsx` | ✅ implementada |
| 20 | Mapa 3: vialidades cercanas | Los datos viven (Overpass → `movimiento_acceso.vialidades` con distancia, y lista en el reporte), pero **no hay un mapa de vialidades como tal** ni capa de vialidades en `Mapa.tsx` | ⚠️ parcial (datos y lista sí; mapa dedicado no) |
| 21 | Mapa 4: minimapa corredor vial | El proxy vehicular existe con rango y nivel /100 (ver #33) y el bloque «Movimiento y acceso» lo presenta con sellos; no se localizó un minimapa cartográfico de corredor separado | ⚠️ parcial (bloque de movilidad sí; minimapa propio no) |
| 22 | Mapa 5: minimapa flujo peatonal | Ídem #21 para el proxy peatonal | ⚠️ parcial (bloque de movilidad sí; minimapa propio no) |
| 23 | Isócronas reales 5/10/15 min | Conector `app/connectors/valhalla.py` + `build_report_context` (polígonos + población + competidores por isócrona) + mapa con zoom por modo en `Reporte.tsx`; sin servicio, fallback a radios **etiquetados como radios** | ✅ implementada |
| 24 | Tabla de mercado por isócrona + «cómo usar este alcance» | `area_alcance_tiempo` del payload (población/competidores por modo) + texto `como_usarla` del builder | ✅ implementada |
| 25 | Entorno comercial: total a 2 km | `build_report_context` → `entorno_comercial.total_negocios` (chequeo b) | ✅ implementada |
| 26 | Entorno: dona por categoría | `Reporte.tsx`: ECharts `type:'pie'` con radios de dona sobre las 9 categorías | ✅ implementada |
| 27 | Entorno: acordeones por categoría con ejemplos | `Reporte.tsx`: `Accordion` por categoría con conteo y top-3 ejemplos del payload | ✅ implementada |
| 28 | Población total del radio | Agregación AGEB en `build_report_context` → `poblacion_viviendas` (chequeo b) | ✅ implementada |
| 29 | Desagregación por sexo y edad (0–14/15–29/30–59/60+) | `poblacion_viviendas.detalle.grupos_edad` y `por_sexo` (chequeo b: 30_59=11000, femenina=12500) | ✅ implementada |
| 30 | Movimiento: actividad económica (PEA ocupada y %) | `build_report_context` → `movimiento_acceso.movilidad.actividad` (`pea_ocupada`, `pct_sobre_pob_15_mas`), enlazado a Aprende «actividad» | ✅ implementada |
| 31 | NSE «Perfil de gasto detectado» (AMAI 2024) | La **lectura** está: banda predominante del AGEB → `nse_etiqueta` con referencia AMAI 2024 (chequeo b). Pero el **cálculo** del proxy AMAI en el ETL `app/etl/jobs/censo_ageb.py` sigue como TODO stub: con datos ingeridos por ETL (no seed) la banda puede venir vacía | ⚠️ parcial (reporte sí; ETL censal no calcula NSE) |
| 32 | Vialidades con distancia y tiempo en auto | Distancia sí (Overpass, chequeo b); el **tiempo en auto por vialidad** no viene en el payload (las vialidades traen nombre/tipo/distancia; los tiempos viven en las isócronas de Valhalla) | ⚠️ parcial (falta tiempo por vialidad) |
| 33 | Movilidad vehicular estimada (rango + nivel /100) | `app/analytics/movilidad.py::proxy_vehicular` (§3.10), siempre con sello «estimado» (chequeo b) | ✅ implementada |
| 34 | Movilidad peatonal estimada | `app/analytics/movilidad.py::proxy_peatonal` (§3.10), rango ±30 % y sello «estimado» | ✅ implementada |
| 35 | Bloque de delivery por giro | `sector_data` (bandera delivery por ficha) + bloque condicional `delivery` del payload (chequeo b: `aplica=true` en cafetería) | ✅ implementada |
| 36 | Fuentes y datos utilizados (lista nominal) | `fuentes_datos.fuentes` con rol por fuente (chequeo b: INEGI Censo 2020, DENUE, …) + ediciones reales | ✅ implementada |
| 37 | Veredicto explícito con factores | `builder.decidir_veredicto` (preexistente, supera a la referencia) | ✅ implementada |
| 38 | ISM | `app/analytics/ism.py` por anillo (preexistente) | ✅ implementada |
| 39 | TAM con supuestos del giro | `app/analytics/tam.py` + supuestos desde la ficha sectorial (con override manual que gana sobre la ficha; cubierto por la suite de Sección 1) | ✅ implementada |
| 40 | Negocios ancla: detección y lista | `app/analytics/anclas.py` (catálogo de pesos/radios) → `negocios_ancla.items` (chequeo b: conveniencia, farmacia de descuento) | ✅ implementada |
| 41 | Efecto ancla en Huff | `aplicar_efecto_ancla` (`A_j' = A_j × (1 + Σ w_a)`) aplicado en `compute_location_analysis` | ✅ implementada |
| 42 | Calculadora de renta (precio/m² × superficie) | `Reporte.tsx::CalculadoraRenta` interactiva | ✅ implementada |
| 43 | Calculadora de punto de equilibrio | `Reporte.tsx::CalculadoraEquilibrio` con plantilla de costos del giro, editable y recálculo en vivo; payload `punto_equilibrio` (chequeo b) | ✅ implementada |
| 44 | Casos de uso de los 15 giros frecuentes | `sector_data.py`: 15 fichas (32 claves con alias) con SCIAN múltiples, editorial, supuestos TAM y plantilla de equilibrio | ✅ implementada |
| 45 | Fuentes del creador (Places, INEGI, SCINCE, DENUE, TomTom) | DENUE ✅ real; INEGI ⚠️ (datos sí, ETL stub, ver #31) | 📌 excepción declarada (§2 del documento rector: Google Places/TomTom/SCINCE son conectores opcionales con stub honesto; el núcleo opera con INEGI + OSM, regla CON-01) |
| 46 | Comparador de ubicaciones | `POST /analysis/compare` forma `items` (2–6, acepta puntos directos sin investigación previa y las deja en Historial, declarado) + ganadora persistente `es_principal` (PATCH que desmarca las demás). La forma heredada por `investigation_ids` sigue en 2–5 | ✅ implementada |
| 47 | Vertical inmobiliaria «Rastreador» | `Reporte.tsx`/`ReportePrint.tsx`: `ReporteCuerpo modoInmobiliario` prioriza entorno/anclas/vialidades y oculta bloques operativos, **pero** el tipo se resuelve con un puente de `localStorage` (`geis:reporte-inv:{reportId}` que escribe `Analizar.tsx`): si el reporte se abre desde Historial o en otro navegador sin ese puente, el modo no se activa; el backend no genera un payload diferenciado | ⚠️ parcial (puente de localStorage frágil; sin diferenciación en backend) |
| 48 | Paquetes por análisis ($199–$899) | Sin módulo de paquetes/créditos/pagos; el conteo de análisis queda en Historial | 📌 excepción declarada (§2 del documento rector: fuera del núcleo open source, SRS NR-06) |
| 49 | Conectar el agente al flujo comercial (API keys/webhooks) | La API FastAPI es el flujo conectable y la sync CRM vive en la Sección 2; sin API keys por usuario ni webhook «reporte listo» | 📌 excepción declarada (§2 del documento rector: fase 2) |
| 50 | Contenido «Aprende» (4 explicadores) | `frontend/src/pages/Aprende.tsx` (competencia, movimiento, población, actividad) + enlaces «¿qué es esto?» desde los bloques de `Reporte.tsx` | ✅ implementada |
| 51 | Historial de análisis | `Historial.tsx` + `GET /investigations` + reportes persistidos (preexistente) | ✅ implementada |
| 52 | Mapa interactivo con capas conmutables | `Mapa.tsx`: capas DENUE, leads, calor IDT, temperatura, líneas Radar **+ nuevas: atractores e isócronas del reporte**; faltan capa de vialidades y capa AGEB/demografía | ⚠️ parcial (faltan vialidades y AGEB) |
| 53 | Densidad de competencia / mapa de calor del giro (KDE) | No hay superficie KDE del giro: la capa de calor sigue siendo IDT y el componente `densidad` del scoring es un proxy por conteo, no una KDE §3.6 | ⚠️ parcial (sin KDE real) |

---

## 3. Trazabilidad completa — Inventario Radar (Sección 2)

**Resumen: 75 ✅ · 23 ⚠️ · 4 📌** (de 102).
Convención: «equivalente GEIS» = la función vive en la arquitectura fusionada
(API `/api/v1` + workflows n8n + SPA React) en vez de en el
`dashboard/server.js` + Express del repo original; cuando la forma difiere de
la función, se dice en el motivo.

### A. Infraestructura y arranque (#1–#9)

| # | Función | Dónde vive ahora | Estado |
|---|---|---|---|
| 1 | Stack Docker completo local $0 | `docker-compose.yml` GEIS: 7 servicios (db PostGIS, redis, api, web, n8n, scraper, cloudflared) | ⚠️ parcial (superconjunto funcional, topología distinta: BD única GEIS en vez de `radar`+`n8n`, dashboard dividido en web+API) |
| 2 | Esquema inicial de BD + seed de providers | Migraciones Alembic 0001–0006 + `app/seed.py` (tablas equivalentes en `prod`/`stg`: leads, leads_raw, runs, providers, linkedin_stats, warm_signals, proposals) | ⚠️ parcial (equivalente por migraciones; no es el `db/init.sql` del repo) |
| 3 | Migración idempotente para volúmenes viejos | Alembic versionado (cadena verificada en el chequeo e) | ⚠️ parcial (no existe el `migrate.sql` del repo ni se localizó la limpieza de filas `EJEMPLO - %`) |
| 4 | Auto-migración al arrancar el dashboard | Arranque del API/compose con Alembic + seed | ⚠️ parcial (no hay `initDb()` de un dashboard Node porque ese servicio no existe en GEIS; limpieza `EJEMPLO - %` no localizada) |
| 5 | Túnel público Cloudflare | Servicio `cloudflared` en `docker-compose.yml` | ✅ implementada |
| 6 | Variante protegida del túnel (PIN por email) | No localizada: `--allowed-mail` solo aparece citado en el propio inventario | ⚠️ parcial (quick tunnel sí; variante protegida no) |
| 7 | Backup de la BD | Hay procedimiento con `pg_dump` en `docs/deployment.md` | ⚠️ parcial (no verificado el procedimiento completo equivalente: restore + respaldo del volumen `n8n_data`) |
| 8 | Configuración solo por `.env` | `.env` del compose + `app/core/config.py`; la UI nunca muestra valores (verificado en LinkedIn/providers) | ✅ implementada |
| 9 | Prune de ejecuciones n8n a 7 días | No localizado `EXECUTIONS_DATA_PRUNE` en `docker-compose.yml` | ⚠️ parcial (no verificado en el compose GEIS) |

### B. Workflow 01 — Radar scrape (#10–#15) · `n8n/workflows/01-radar-scrape.json` (10 nodos)

| # | Función | Dónde vive ahora | Estado |
|---|---|---|---|
| 10 | Triple trigger (Manual + cron lun 6:00 + Webhook) | Nodos Manual, «Lunes 6am» (`0 6 * * 1`) y «Webhook radar-01» verificados en el JSON | ✅ implementada |
| 11 | Armar búsquedas (6 = 3 queries × 2 corredores, 40 c/u) | Nodo Code «Armar búsquedas» | ✅ implementada |
| 12 | Llamada al scraper por combinación | Nodo HTTP «Scrapear Maps» | ✅ implementada |
| 13 | Normalizar + dedup en lote | Nodo Code «Normalizar» (giro = query, `fuente='google_maps'`, dedup `lower(nombre\|direccion)`) | ✅ implementada |
| 14 | Guardar en `leads_raw` | Nodo Postgres «Guardar en raw» (destino GEIS: `stg.leads_raw`) | ✅ implementada |
| 15 | Cierre de corrida que desbloquea la 02 | Nodos «Registrar run (GEIS)» (HTTP a `/pipelines/run/...`) + «Callback Run OK»; el gating R10 lee esas corridas | ✅ implementada |

### C. Microservicio scraper (#16–#22) · `scraper/app.py`

| # | Función | Dónde vive ahora | Estado |
|---|---|---|---|
| 16 | `GET /health` del scraper | `scraper/app.py::health()` (`mode`, `provider`, `apify_token: bool`) | ✅ implementada |
| 17 | `POST /scrape` contrato único | `scraper/app.py::scrape()` (mismo contrato; trae además un modo `demo` extra) | ✅ implementada |
| 18 | Backend por request desde tabla `providers` (caché 60 s) | `scraper/app.py::resolver_backend()` (lee BD/env, override `SCRAPER_PROVIDER`) | ✅ implementada |
| 19 | Backend local Playwright | `scraper/app.py::scrape_local()` | ✅ implementada |
| 20 | Extracción por ficha best-effort | `scrape_local()` (h1, `data-item-id`, regex de rating y de `@lat,lng`) | ✅ implementada |
| 21 | Backend nube Apify | `scraper/app.py::scrape_apify()` (actor `apify/google-maps-scraper`, poll de estado) | ✅ implementada |
| 22 | Uso responsable anti-bloqueo | `pausa()` con delays aleatorios 2–5 s + límites de scroll del código portado | ✅ implementada |

### D. Workflow 02 — Dedup + score (#23–#39) · `n8n/workflows/02-dedup-score.json` (23 nodos)

| # | Función | Dónde vive ahora | Estado |
|---|---|---|---|
| 23 | Doble trigger (Manual + Webhook, sin cron) | Manual + «Webhook radar-02» presentes, **más un tercer trigger** «Lunes 6:30am» que el original no tenía | ⚠️ parcial (trae un cron extra lun 6:30 no presente en el original) |
| 24 | Dedup SQL atómico | Nodo «Insertar con dedup»: `NOT EXISTS` con `lower()` en nombre y dirección (verificado; GEIS lo acota además a `source='gmaps'`) | ✅ implementada |
| 25 | Score base +15 web / +20 giro (R2) | Mismo nodo, `CASE` en el SELECT verificado línea por línea | ✅ implementada |
| 26 | Sector derivado del giro (R3) | Sin equivalente: `prod.leads` GEIS **no tiene columna `sector`** y el INSERT no lo deriva (la lógica de giro vive en la línea/scoring) | ⚠️ parcial (sector no persiste) |
| 27 | Selección clima (sin temp, con coords, tope 60) | Nodo «Leads sin temperatura» | ✅ implementada |
| 28 | Temperatura vía Open-Meteo | Nodo HTTP «Open-Meteo» con `onError: continue` | ✅ implementada |
| 29 | Bonus por calor + línea por mes (R4/R5) | Nodo Code «Score y línea» verificado: `temp > 30` estricto → +20; feb–jun koolkat primero; regex solar sin `super` | ✅ implementada |
| 30 | Actualización del lead con `LEAST(…,100)` | Nodo «Actualizar lead» | ✅ implementada |
| 31 | Leer provider de enriquecimiento (si falla, sigue) | Nodo «Leer provider enrichment» con `onError: continue` verificado | ✅ implementada |
| 32 | Gate Apollo (solo cloud+apollo) | Nodo IF «¿Apollo activo?» | ✅ implementada |
| 33 | Selección Apollo top 20 | Nodo «Top 20 con web» | ✅ implementada |
| 34 | Extracción de dominio | Nodo Code «Extraer dominio» | ✅ implementada |
| 35 | Enriquecimiento Apollo (error no tumba) | Nodo HTTP «Apollo org enrich» con `onError: continue` verificado | ✅ implementada |
| 36 | Bonus por empleados (≥200:+15, ≥50:+10) | Nodo Code «Merge Apollo» | ✅ implementada |
| 37 | Guardar enrich (COALESCE + LEAST + marca) | Nodo «Guardar enrich», SQL verificado (`empleados_est = COALESCE(...)`, `score = LEAST(score + bonus, 100)`, `enriquecido_apollo = true`) | ✅ implementada |
| 38 | Idempotencia (marcar raw procesados) | Nodo «Marcar raw procesados» | ✅ implementada |
| 39 | Cierre de corrida 02 | Nodos «Registrar run (GEIS)» + «Callback Run OK» | ✅ implementada |
| — | Nodo extra GEIS (no es fila del inventario) | Nodo HTTP «Enriquecer geografía (opcional)» → `POST /leads/enrich-geo` tras el scoring, como pidió el documento rector §3.2 | ✅ implementada |

### E. Workflow 03 — Caza señales (#40–#48) · `n8n/workflows/03-signal-catcher.json` (17 nodos)

| # | Función | Dónde vive ahora | Estado |
|---|---|---|---|
| 40 | Triple trigger (Manual + diario 7:00 + Webhook) | Verificados en el JSON (`0 7 * * *`) | ✅ implementada |
| 41 | Lectura de `signals/input.json` | Nodo «Leer signals/input.json» (Read Binary File) | ✅ implementada |
| 42 | Parseo de señales | Nodos «Parsear JSON» + Code «Parsear señales» | ✅ implementada |
| 43 | Upsert +25 por señal manual (R6) | Nodo «Upsert +25», SQL verificado: UPDATE con `LEAST(score+25,100)` y `etapa='nuevo'` + INSERT con score 25 si no existe (semántica equivalente al `ON CONFLICT` original; sin columna sector, ver #26) | ✅ implementada |
| 44 | Leer warm signals pendientes (tope 50) | Nodo «Leer warm signals» con `onError: continue` verificado | ✅ implementada |
| 45 | Armar warm (solo con `empresa_ref`) | Nodo Code «Armar warm» | ✅ implementada |
| 46 | Upsert +25 por señal cálida | Nodo «Upsert warm +25» | ✅ implementada |
| 47 | Marcar warm procesadas | Nodo «Marcar warm procesadas» | ✅ implementada |
| 48 | Cierre + Resumen | Nodos «Registrar run (GEIS)» + Set «Resumen» | ✅ implementada |

### F. Workflow 04 — Sync CRM (#49–#57) · `n8n/workflows/04-crm-sync.json` (18 nodos)

| # | Función | Dónde vive ahora | Estado |
|---|---|---|---|
| 49 | Trigger Manual + Webhook; inactivo hasta CRM nube | Nodos presentes; la «inactividad» del original se reproduce con el gate de provider (#50): en local es no-op con Run OK | ✅ implementada |
| 50 | Leer provider CRM + gate «Fin local» | Nodos «Leer provider crm», IF «¿Nube activa?», Code «Fin local» | ✅ implementada |
| 51 | Selección a sincronizar (tope 100) | Nodo «Leads para sync» | ✅ implementada |
| 52 | Rama HubSpot / Twenty | Nodo IF «¿HubSpot?» | ✅ implementada |
| 53 | Payload HubSpot con propiedades `biokool_*` | Nodo Code «Preparar payload» | ✅ implementada |
| 54 | Upsert HubSpot (error no tumba) | Nodo HTTP «HubSpot upsert» con `onError: continue` verificado | ✅ implementada |
| 55 | Marcaje de sincronizados | Nodos IF «¿OK?», Code «Marcar sync», Postgres «Ejecutar marcaje» | ✅ implementada |
| 56 | Twenty stub | Nodo Code «Twenty stub» | ✅ implementada |
| 57 | Cierre de corrida 04 | Nodos «Registrar run (GEIS)» + «Callback Run OK» | ✅ implementada |

### G. Workflow 05 — LinkedIn (#58–#70) · `n8n/workflows/05-linkedin-signals.json` (26 nodos)

| # | Función | Dónde vive ahora | Estado |
|---|---|---|---|
| 58 | Triple trigger (Manual + lun 8:00 + Webhook) | Verificados en el JSON (`0 8 * * 1`) | ✅ implementada |
| 59 | Leer config LinkedIn + gate activo | Nodos «Leer config linkedin», IF «¿Activo?», Code «Fin (inactivo)» | ✅ implementada |
| 60 | Chequeo de token con motivos explícitos | Nodo Code «Checar token» + IF «¿Token vigente?» | ✅ implementada |
| 61 | Aviso de reconexión en `warm_signals` | Nodos «Aviso token» + «Insertar aviso» | ✅ implementada |
| 62 | Stats previas (delta de seguidores) | Nodo «Stats previas» | ✅ implementada |
| 63 | Seguidores actuales (API LinkedIn) | Nodo HTTP «Stats seguidores» (código portado; no ejecutable sin token real) | ✅ implementada |
| 64 | Posts recientes (10) | Nodo HTTP «Posts recientes» | ✅ implementada |
| 65 | Engagement top 5 (likes + comentarios) | Nodos «Top 5 URNs», «Likes», «Juntar likes», «Comments», «Juntar todo» | ✅ implementada |
| 66 | Detección de señales cálidas (R9) | Nodo Code «Detectar señales» verificado: seguidores nuevos ≥ 3 y posts con likes+comentarios ≥ 5 | ✅ implementada |
| 67 | Guardar stats del día (upsert por org/fecha) | Nodo «Guardar stats» | ✅ implementada |
| 68 | Guardar señales en `warm_signals` | Nodo «Guardar warm» | ✅ implementada |
| 69 | Cierre + `onError: continue` en casi todo | Verificado: 10 nodos de la 05 con `onError: continueRegularOutput` + «Registrar run (GEIS)» | ✅ implementada |
| 70 | Alcance honesto de LinkedIn documentado | Sticky «Nota: alcance LinkedIn» en el workflow + notas en `Operacion.tsx`, `Sistema.tsx` y `PanelRadar.tsx` («la API no permite buscar prospectos») | ✅ implementada |

### H. API del dashboard (#71–#87) → equivalentes GEIS

| # | Función | Dónde vive ahora | Estado |
|---|---|---|---|
| 71 | Lista de leads (score desc, filtro etapa) | `GET /leads/curados` (+ filtros línea/source y los 5 geo nuevos) y `GET /leads/count` | ✅ implementada |
| 72 | Detalle de un lead | `GET /leads/curados/{lead_id}` | ✅ implementada |
| 73 | Actualizar etapa/notas de un lead | `PATCH /leads/curados/{lead_id}` (validación de etapa en backend; usado por el drawer) | ✅ implementada |
| 74 | Bitácora combinada (locales + ejecuciones n8n) | `GET /pipelines/runs` devuelve las corridas locales (GEIS); **no se localizó** la fusión con las últimas 20 ejecuciones de la API de n8n ni el campo `n8nError` | ⚠️ parcial (solo bitácora local) |
| 75 | Ejecutar etapa con gating (R10) | `POST /pipelines/run/{stage}`: 400 si la etapa no existe, **409 con motivo diferenciado** (nunca/running/error) si la previa no está en `ok`; registra `running` y dispara el webhook | ✅ implementada |
| 76 | Lista de providers con metadatos de UI | `GET /providers` devuelve los providers de BD; el catálogo de etiquetas/descripciones/modos/backends vive **hardcodeado en el frontend** (`Sistema.tsx`), no en la respuesta de la API | ⚠️ parcial (funciona en UI; contrato distinto) |
| 77 | Cambiar provider (validación + coherencia R11) | Es **PUT** `/providers/{name}` (no PATCH); la `config` se **reemplaza**, no se fusiona con la existente como en el original; la coherencia se valida solo si `mode` y `provider` vienen juntos en la misma petición | ⚠️ parcial (tres desviaciones verificadas en `providers.py`) |
| 78 | Catálogo de workflows (5 etapas) | `GET /pipelines/workflows` (lee los JSON de `n8n/workflows/`) | ✅ implementada |
| 79 | `GET /api/config` sin secretos | **No existe** endpoint `/config` (verificado en el volcado OpenAPI); la tarjeta de Sistema lo declara y muestra «n/d» en versión, webhooks y keys Radar | ⚠️ parcial (endpoint ausente; UI honesta) |
| 80 | Proxy de clima con caché 6 h | `GET /geo/weather`: caché en memoria TTL 6 h ✅; la clave se redondea a **3 decimales** (original: 2) y la respuesta trae solo temperatura actual (sin máximas diarias a 3 días) | ⚠️ parcial (desviaciones menores) |
| 81 | Health con 5 checks | `GET /system/health`: postgres, n8n, scraper y resumen de providers; **sin check de cobertura de líneas** en el backend (esa alerta la calculan Panel y Sistema en el frontend desde conteos por línea) y con timeout de 2 s (original: 5 s) | ⚠️ parcial (cobertura no vive en el health) |
| 82 | Registrar señal del SDR | `POST /signals` guarda en la tabla `warm_signals` con `{titulo, detalle, empresa_ref, fuente}`; **no** escribe `signals/input.json` ni usa el shape `{empresa, giro, tipo, evidencia}` del original (el resultado es equivalente: la 03 lo procesa con +25 por la rama warm) | ⚠️ parcial (equivalente funcional, contrato y persistencia distintos) |
| 83 | OAuth LinkedIn: iniciar | `GET /integrations/linkedin/auth` devuelve `{auth_url}` en JSON (no redirige); scopes `r_organization_social` + `w_organization_social` (el original pedía además `openid profile` y `r_organization_admin`); sin config responde **501** (original: 400) | ⚠️ parcial |
| 84 | OAuth LinkedIn: callback | Intercambia el `code`, pero **no guarda los tokens en `providers.config`** ni activa `mode='cloud'`: el token ni siquiera se devuelve por la API; hay que copiarlo a `LINKEDIN_ACCESS_TOKEN` en el entorno. Sin página HTML de confirmación (responde JSON) | ⚠️ parcial |
| 85 | Estado de LinkedIn sin secretos | `GET /integrations/linkedin/status` devuelve solo `{connected, scopes_requeridos, nota}`: **no expone** `expira`/`expirado`, `org_id`, `tieneClientId/Secret`, stats de 7 días ni warm signals pendientes. Consecuencia: la alerta «Token de LinkedIn expirado» del Panel y los stats de la tarjeta existen en el frontend pero **nunca se alimentan** | ⚠️ parcial (status mínimo; expiración no expuesta) |
| 86 | Desconectar LinkedIn | `POST /integrations/linkedin/disconnect` limpia solo la variable del **proceso**; si el token está en `.env`/vault hay que borrarlo ahí (la propia respuesta lo declara) | ⚠️ parcial (desconexión no persistente) |
| 87 | Servir la SPA | Servicio `web` del compose (build Vite verificado en §1.2) | ✅ implementada |

### I. Frontend del dashboard (#88–#97) → SPA GEIS

| # | Función | Dónde vive ahora | Estado |
|---|---|---|---|
| 88 | SPA de 5 vistas con navegación | SPA React con selector de 2 secciones: las 5 vistas del Radar viven como Panel Radar, Operación, Leads, Mapa (`?modo=radar`) y Sistema, junto a las de Ubicaciones y las comunes | ✅ implementada |
| 89 | Tema claro/oscuro persistido | `ThemeToggle.tsx` con `localStorage` (clave GEIS `geis-theme`; la del original era `radar-theme`) y re-tematizado de gráficas | ✅ implementada |
| 90 | Indicador de conexión en el header | No se localizó un dot de conexión permanente en `Topbar`/`AppLayout`; la salud se consulta en Inicio, Panel Radar y Sistema, pero no como indicador siempre visible | ⚠️ parcial (sin dot en el header) |
| 91 | Badge de leads en el menú + dot de advertencia en Sistema | El badge de total de leads en el Sidebar **sí** (vía `/leads/count`); el dot de advertencia sobre «Sistema» cuando el health falla **no se localizó** | ⚠️ parcial (badge sí; dot de Sistema no) |
| 92 | Toasts de éxito/error | `sonner` en toda la SPA (confirmado en Leads, Operación, Reporte, Mapa) | ✅ implementada |
| 93 | Modal genérico reutilizable | Componente `Dialog` usado para confirmar etapa, registrar señal y desconectar LinkedIn | ✅ implementada |
| 94 | Polling suave cada 25 s | `Operacion.tsx`: `setInterval` 25 000 ms con pausa si `document.hidden` (verificado) | ✅ implementada |
| 95 | Normalización de teléfono MX (`normPhone`) | `frontend/src/lib/apiGeo.ts::normPhone` — reglas idénticas (10 dígitos → `52`, etc.), usada por el drawer de Leads | ✅ implementada |
| 96 | Normalización de URL (`normWeb`) | `frontend/src/lib/apiGeo.ts::normWeb` | ✅ implementada |
| 97 | «Por qué este lead» (`whyLinea`) | `frontend/src/lib/apiGeo.ts::whyLinea` con la regex solar **con `super`** (como la explicación original) + render en el drawer de `Leads.tsx` | ✅ implementada |

### J. Fase 2 / diseño (#98–#102)

| # | Función | Dónde vive ahora | Estado |
|---|---|---|---|
| 98 | Tabla `proposals` (gancho fase 2) | El backend GEIS **sí** la implementa: CRUD completo en `/proposals` (POST/GET/PATCH/DELETE); ninguna pantalla del frontend la consume todavía | ⚠️ parcial (API sí; UI no) |
| 99 | Provider `email` (fase 2, dominios dedicados) | Sin implementar, como en el diseño original | 📌 excepción declarada (fase 2 del propio repo, §J del inventario) |
| 100 | Automatizar señales (Alerts/scraping → input.json) | Sin implementar | 📌 excepción declarada (fase 2 del propio repo) |
| 101 | WhatsApp API oficial + bot calificador | Sin implementar (el WhatsApp que existe es `wa.me` manual, como manda R15) | 📌 excepción declarada (fase 2 del propio repo) |
| 102 | Calibración con datos reales del piloto | Sin implementar (requiere el piloto corriendo) | 📌 excepción declarada (fase 2 del propio repo) |

---

## 4. Reglas de negocio R1–R17 — estado verificado

| Regla | Estado | Evidencia |
|---|---|---|
| R1 · Tope universal 100 | ✅ | `LEAST(score + bonus, 100)` en los nodos de la 02 (Apollo), la 03 (+25) verificados; el score del backend (`scoring_unificado`) es una media ponderada normalizada, acotada 0–100 por construcción (modelo distinto, mismo tope) |
| R2 · Score base +15 web / +20 giro | ✅ | SQL del nodo «Insertar con dedup» de la 02 inspeccionado |
| R3 · Sector derivado del giro | ⚠️ | No hay columna `sector` en `prod.leads` GEIS ni derivación al insertar (ver Radar #26) |
| R4 · Bonus clima > 30 °C estricto | ✅ | JS de «Score y línea» verificado (`temp > 30 ? 20 : 0`, solo leads sin temperatura, tope por el nodo de selección) |
| R5 · Línea por mes | ✅ | JS verificado: feb–jun koolkat (evaluado primero, gana en febrero), oct–feb solar solo con regex `/gasolin\|estacionamiento\|comercial\|plaza\|tienda/` (sin `super`), resto evaporativa; `linea_recomendada` del backend y `whyLinea` del frontend son consistentes (la explicación sí incluye `super`, como en el original) |
| R6 · Señales +25 | ✅ | SQL de la 03 verificado: crea con 25 o suma con `LEAST` **y regresa la etapa a `nuevo`** (comportamiento conservado a propósito, §3 del documento rector); las señales de `input.json` se re-aplican en cada corrida 03 (no se marcan), también conservado |
| R7 · Bonus Apollo | ✅ | Nodos Apollo de la 02 con guardar `LEAST` + `COALESCE` verificados; top 20 y marca `enriquecido_apollo` por estructura del workflow |
| R8 · Dedup `(nombre, direccion)` | ✅ | `NOT EXISTS` con `lower()` en ambos campos al insertar + dedup en lote en la 01; la constraint GEIS es `UNIQUE(source, nombre, direccion)` (superconjunto del original: misma identidad dentro de cada fuente) |
| R9 · Señales cálidas LinkedIn | ✅ | JS de «Detectar señales» (05) verificado: ≥ 3 seguidores nuevos; post con likes+comentarios ≥ 5 con link |
| R10 · Gating de corridas | ✅ | Backend `pipelines.py`: mapa de predecesores exacto (02←01, 03←02, 04←02, 01/05 libres), 409 con motivo diferenciado nunca/running/error; frontend `Operacion.tsx` deshabilita el botón con el mismo motivo y 🔒; cubierto por la suite de Sección 2 |
| R11 · Coherencia de providers | ⚠️ | `PUT /providers/{name}` rechaza (422) el par incoherente **solo si `mode` y `provider` vienen juntos**; un cambio de un solo campo no se bloquea (decisión documentada en el propio código). El frontend compensa eligiendo automáticamente el backend coherente al cambiar el modo |
| R12 · El núcleo nunca depende de la nube | ✅ | `onError: continueRegularOutput` verificado en los nodos nube de 02 (Apollo, Open-Meteo), 03 (warm), 04 (HubSpot) y casi toda la 05; los datos aterrizan primero en Postgres y el CRM es espejo |
| R13 · Clima en el dashboard | ⚠️ | Caché de 6 h ✅ en `/geo/weather`, pero la clave se redondea a 3 decimales (original: 2) y el círculo térmico del Mapa usa radio en píxeles proporcional a la temperatura (`max(6, temp×1.2)` en `circleMarker`), no la fórmula en metros `max(2500, (temp−18)×1800)` |
| R14 · Cobertura de líneas en el health | ⚠️ | La alerta existe y con el mensaje correcto («corre la 01/02 o revisa la regla de línea por mes») en Panel Radar y en Sistema, pero la **calcula el frontend** desde `/leads/count` por línea: `GET /system/health` no trae el check de cobertura |
| R15 · «El Radar propone, tú decides» | ✅ | Ningún flujo envía mensajes solo: el contacto es manual desde el drawer (Llamar/WhatsApp/LinkedIn) y las señales solo suman score |
| R16 · Email frío nunca desde `@biokool.mx` | 📌 | Regla de fase 2 (ver Radar #99): el provider `email` sigue apagado y nada en el sistema envía correo; la regla queda como diseño documentado |
| R17 · ICP y calendario comercial | ✅ | Reflejados en la lógica de línea por mes (R5), `whyLinea` y las fichas de línea del backend (`scoring_unificado`): Koolkat feb–jun, Solar oct–feb en giros al aire libre, Evaporativa todo el año |

**Resumen R1–R17: 12 ✅ · 4 ⚠️ (R3, R11, R13, R14) · 1 📌 (R16).**

---

## 5. Pendientes honestos consolidados

Lo que esta validación **no** pudo comprobar o encontró incompleto, en orden
de impacto:

1. **Nada se ejecutó contra Postgres real ni contra n8n.** Toda la
   validación funcional usó sesiones fake/TestClient (la VM no corre
   Docker). El SQL espacial de `build_report_context` y de
   `POST /leads/enrich-geo` (join con AGEBs por contención, DENUE ≤ 500 m),
   las migraciones 0005/0006 aplicadas sobre una BD real y el recorrido de
   los 5 workflows importados en n8n quedan **por confirmar en la máquina
   de Chino** (`docker compose up`, `alembic upgrade head`, correr la 01).
2. **Servicios externos no ejercitados en vivo:** Valhalla (isócronas
   reales), Overpass (vialidades), Nominatim (geocoding/reverse) y
   Open-Meteo se validaron con mocks. El código y los fallbacks honestos
   están (radios etiquetados, 422 sin punto falso), pero la primera corrida
   real puede revelar tiempos de respuesta o formatos no previstos.
3. **LinkedIn es la zona más parcial de la Sección 2** (Radar #83–#86):
   el status no expone expiración/org/stats (la alerta de token expirado
   del Panel nunca se alimenta), el callback no persiste tokens (hay que
   copiarlos al `.env` a mano) y disconnect solo limpia el proceso.
4. **Sin endpoint `/config`** (Radar #79): la tarjeta «Configuración
   técnica» de Sistema muestra «n/d» en versión, webhooks y keys Radar
   porque la API no expone presencia de esas variables.
5. **Providers con desviaciones de contrato** (Radar #76, #77): es PUT y
   no PATCH, la `config` se reemplaza en vez de fusionarse, el catálogo
   de metadatos vive en el frontend y la coherencia R11 solo se valida
   con el par completo (R11 ⚠️).
6. **Modo inmobiliario frágil** (Sabueso #47): depende del puente de
   `localStorage` `geis:reporte-inv:{id}`; abrir el reporte sin pasar por
   Analizar en el mismo navegador pierde el modo. Lo robusto sería
   resolver el tipo en el backend al leer el reporte.
7. **ETL censal sin NSE ni ingesta real** (Sabueso #31, #45):
   `censo_ageb.py` sigue con el TODO del proxy AMAI; con datos que no
   vengan del seed, la sección NSE del reporte puede salir vacía.
8. **Mapas de Sabueso incompletos** (#20–#22, #52, #53): faltan el mapa de
   vialidades y los minimapas de corredor/peatonal como piezas
   cartográficas, la capa de vialidades y la de AGEB en el Mapa general,
   el tiempo en auto por vialidad (#32) y una KDE real de competencia.
9. **Sector del lead no persiste** (Radar #26 / R3) y la bitácora no
   fusiona las ejecuciones de n8n (Radar #74): dos datos del dashboard
   original que hoy no tienen equivalente.
10. **Detalles menores verificados:** prune de ejecuciones n8n no
    localizado en el compose (Radar #9); variante protegida del túnel y
    limpieza `EJEMPLO - %` no localizadas (#6, #3); la 02 trae un cron
    extra lun 6:30 (#23); el clima redondea la clave a 3 decimales y sin
    máximas diarias (R13/#80); sin dot de conexión en el header ni dot de
    advertencia en «Sistema» (#90, #91); `proposals` tiene API completa
    pero ninguna pantalla la usa (#98); chunk del frontend de 2.19 MB sin
    code-splitting (aviso de Vite, no error).
11. **Fase 2 declarada (no son fallos):** paquetes/pagos Sabueso #48
    (NR-06), conectores Places/TomTom/SCINCE #45, API keys/webhooks #49 y
    Radar #99–#102, conforme a las excepciones del documento rector §2 y
    al §J del inventario Radar.

---

## 6. Conclusión del validador

La restructuración **cumple lo verificable**: 135/135 tests (97 previos
intactos + 38 nuevos), build y TypeScript verdes, contrato
frontend↔API con **0 huérfanas**, y los cinco chequeos funcionales pasan
con evidencia (geocoding exacto sin punto falso, reporte con las 14
secciones pobladas, filtros geo que reducen de verdad, share público con
revocación efectiva y cadena Alembic lineal 0001→0006). La trazabilidad
cierra en **117 ✅ · 31 ⚠️ · 7 📌** sobre las 155 filas de ambos
inventarios, con las reglas en **12 ✅ · 4 ⚠️ · 1 📌**. Las parcialidades
son reales pero acotadas y están declaradas fila por fila arriba; ninguna
es un «no existe» disfrazado. Lo único que esta validación no puede
afirmar —y no afirma— es el comportamiento contra Postgres, n8n y los
servicios externos reales: eso se confirma con la primera corrida en la
máquina de Chino.
