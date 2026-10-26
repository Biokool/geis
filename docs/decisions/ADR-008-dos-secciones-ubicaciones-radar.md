# ADR-008: Dos secciones (Ubicaciones / Radar), geocoding real y links invitado

- **Fecha:** 2026-10-21 (diseño) · verificado e integrado el 2026-10-25
- **Estado:** Accepted
- **Autor:** owner (decisión) + workers de Sección 1/2 (implementación)
- **Origen:** fusión GEIS × Biokool Radar; encargo «más funciones con menos clicks, sin humo»

## Contexto

La fusión había quedado como un menú único de cinco grupos que mezclaba dos
productos con flujos distintos: el análisis de ubicaciones (estilo Sabueso IA:
giro + dirección → reporte) y la prospección operativa (estilo Biokool Radar:
scrapeo → score → señales → CRM). El owner pidió separarlos en **dos grandes
secciones** sin perder funciones ni duplicar código.

Los inventarios normativos (`INVENTARIO-SABUESO.md`, 53 filas;
`INVENTARIO-RADAR.md`, 102 filas + R1–R17) fijaron qué debía existir y la
validación (`REVISION-2-SECCIONES.md`) midió la trazabilidad: 117 ✅ · 31 ⚠️ ·
7 📌.

## Problema

1. Un solo menú no cuenta el proceso de ninguno de los dos productos y obliga
   a clicks cruzados.
2. El análisis de ubicaciones dependía de un **stub** de geocodificación (punto
   fijo del Zócalo) y de un reporte con la mayoría de secciones vacías.
3. Compartir un reporte exigía exportar a mano; no había link de invitado ni
   vista imprimible.
4. El Radar no tenía filtros geográficos (entidad/municipio/colonia/CP/SCIAN)
   porque el repo original no trae esos campos.

## Alternativas consideradas

1. **Dos aplicaciones separadas** — duplica infraestructura, auth, datos y
   mantenimiento; descartado.
2. **Un menú único con subsecciones plegables** — sigue mezclando flujos y no
   resuelve «menos clicks»; descartado.
3. **Un shell común (Inicio + Sistema) con selector de sección persistente** —
   una sola SPA, una sola API, cada sección muestra solo sus pantallas;
   elegido.

## Decisión

1. **Selector fijo 📍 Ubicaciones | 🎯 Radar** arriba del sidebar, persistido en
   `localStorage` (`geis:seccion`) y sincronizado con la ruta. Inicio y el grupo
   Sistema son comunes.
2. **Sección 1 (Ubicaciones):** flujo rey en `Analizar` (giro + dirección o link
   de Maps → geocoding real → pin confirmable → reporte en una pantalla),
   `Reporte` visual, `Mapa`, `Comparador` (2–6, ganadora persistente), `Historial`
   y `Aprende`.
3. **Sección 2 (Radar):** `Panel Radar`, `Operación`, `Leads` (con filtros geo),
   `Mapa Radar` (`?modo=radar`), `KPIs`, `Geofencing`, `Exportación`.
4. **Geocoding real y honesto:** parser de links de Maps + links cortos +
   Nominatim/OSM; si no resuelve → **422**, nunca un punto por defecto.
5. **Reporte completo en el backend:** `build_report_context` agrega INEGI +
   DENUE + conectores OSM (Valhalla para isócronas, Overpass para vialidades;
   si fallan, fallback declarado: radios/vacío, jamás datos inventados).
6. **Compartir:** tokens opacos en `prod.report_shares` (expirables/revocables)
   con ruta pública `/r/{token}`; «PDF» = vista imprimible del navegador.
7. **Filtros geo derivados:** migración 0005 (columnas en `prod.leads`) +
   `POST /leads/enrich-geo` (AGEB por contención + DENUE ≤500 m + regex de CP).
8. **Ganadora persistente** del comparador: `es_principal` en
   `prod.user_investigations` (migración 0006).

## Justificación

Una sola SPA y una sola API conservan la tesis de la fusión (una tabla de
leads, un score, un mapa, un dashboard). El selector reduce el menú visible sin
romper rutas existentes (los enlaces directos siguen funcionando y sincronizan
la sección). El geocoding real y los fallbacks declarados sustituyen el humo por
límites explícitos.

## Consecuencias

- Regla: **cada pantalla nueva declara a qué sección pertenece**; Inicio y
  Sistema son las únicas comunes.
- Los links de Maps y direcciones ahora requieren red (Nominatim). Sin red, el
  flujo responde 422 con mensaje accionable; no hay modo offline de geocoding.
- Overpass puede responder 502 por capacidad: el reporte sale sin vialidades y
  el proxy vehicular usa su basal poblacional (declarado en `metodo`).
- La cobertura de entidad/municipio depende de los AGEB cargados: con el seed
  (4 AGEB) solo se llena una fracción; el ETL censal completo es el pendiente.
- Los datos de compartir son públicos por diseño (solo lectura, token opaco):
  no compartir reportes con información sensible sin revocar el link.
- `backend/app` y `frontend/src` quedan modificados bajo esta autorización
  (excepción registrada, como ADR-004).

## Impacto

- Backend: `app/geo/`, `app/connectors/{overpass,valhalla}.py`,
  `app/analytics/{anclas,categorias,movilidad,sector_data}.py`,
  `app/reports/context.py`, routers `territories`, `reports`, `leads`,
  `analysis`, `catalogs`, `investigations`; migraciones 0005/0006.
- Frontend: `App.tsx`, `Sidebar.tsx`, `lib/apiGeo.ts`, páginas
  `Analizar`, `Aprende`, `PanelRadar`, `ReportePrint`, `ReporteCompartido` y la
  reescritura de `Reporte`.
- n8n: nodo HTTP opcional `enrich-geo` en `02-dedup-score.json`.
- Verificación: 135 tests, build verde, E2E real (ver `changelog.md` 2026-10-25 y
  `REVISION-2-SECCIONES.md`).

## Referencias

- [ARQUITECTURA-2-SECCIONES.md](../ARQUITECTURA-2-SECCIONES.md) ·
  [INVENTARIO-SABUESO.md](../INVENTARIO-SABUESO.md) ·
  [INVENTARIO-RADAR.md](../INVENTARIO-RADAR.md) ·
  [REVISION-2-SECCIONES.md](../REVISION-2-SECCIONES.md) ·
  [ADR-004](ADR-004-frontend-radar-paginacion-dashboard.md)
