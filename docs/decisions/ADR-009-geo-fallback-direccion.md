# ADR-009 — Respaldo geo desde la dirección formateada (enriquecer sin catálogos completos)

- **Estado:** Aceptada (2026-10-26)
- **Ámbito:** `backend/app/api/v1/leads.py` (excepción a AGENTS.md, continuación de la autorización de ADR-008 §Radar)
- **Relacionadas:** ADR-008 (2 secciones), `api/rest.md` (`POST /leads/enrich-geo`)

## Contexto

Los filtros geo de la Sección 2 (entidad/municipio/colonia/CP en Leads, Mapa
y Operación) salían vacíos para la zona scrapeada real (Querétaro) aunque los
leads existieran: `enrich-geo` dependía de `prod.marco_entidades` /
`prod.marco_municipios` (0 filas) y `prod.inegi_agebs` (4 filas del seed), y
la única derivación sin geometría era el CP por regex. El catálogo
`GET /catalogs/geo-filters` deriva de los propios leads, así que el problema
se propagaba a los dropdowns en cascada.

A la vez, la dirección scrapeada por Google Maps ya contiene la geografía en
texto con formato estable: `"Calle y número, Colonia, 76000 Municipio, Abrev."`.

## Decisión

1. **Excepción acotada** a la regla "no tocar `backend/app`" para
   `leads.py`: añadir `_parsear_direccion_geo()`, que extrae de la dirección
   formateada (formato Google MX) el CP con municipio (o la entidad cuando el
   segmento es exactamente su nombre, p. ej. `06000 Ciudad de México`), la
   entidad por abreviatura normalizada (`Qro.`, `B.C.`, `CDMX`, `Méx.`) o
   nombre oficial, y la colonia del segmento previo al CP siempre que no sea
   la calle (primer segmento) ni contenga un CP. `México` a secas es país y
   nunca se clasifica como entidad.
2. **Jerarquía de fuentes intacta:** AGEB (contención) manda; DENUE cercano
   rellena; el texto es **último recurso** y solo rellena campos NULL
   (COALESCE). Nunca pisa lo ya poblado; nunca inventa: si la dirección no
   lo dice, el campo queda vacío.
3. **Detalle del endpoint sin cambios de schema:** `solo_cp` pasa a contar
   los leads sin geometría a los que la dirección dio *algún* dato (antes
   literalmente solo el CP); `sin_datos` cuando no dio ninguno.
4. **Tests:** `test_seccion2.py` extendido (parser, colonia no confundida
   con la calle, país ignorado) — **137 passed**.

## Consecuencias

- ✅ Filtros operativos con datos reales: `entidad=Querétaro` → 82 leads,
  cascada `geo-filters` con municipios/colonias/CPs de Qro.
- ✅ Sin dependencia del ETL censal completo (backlog) para operar la
  Sección 2; cuando el Marco INEGI se cargue, tomará precedencia por diseño.
- ⚠️ Calidad limitada por el texto de Google (colonias atípicas como
  `"Lib. Norponiente Km 18-Bodega A5"` aparecen tal cual en el catálogo).
- ⚠️ `scian` sigue viniendo solo de DENUE cercano: `pendientes` no baja a 0
  (los leads sin SCIAN cercano lo mantienen > 0). Documentado en la
  docstring del endpoint.
