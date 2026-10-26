# ARQUITECTURA — Dos grandes secciones (2026-10-21)

> Decisión de Chino: el sistema se divide en **dos grandes secciones**.
> Sección 1 = **todo** lo de Sabueso IA (plataforma + videos + Instagram).
> Sección 2 = **todo** lo del repositorio Biokool Radar.
> Normativos: `docs/INVENTARIO-SABUESO.md` (53 funciones) y
> `docs/INVENTARIO-RADAR.md` (102 funciones + reglas R1–R17).
> Regla de oro de Chino: **«no necesitamos humo: más funciones con menos clicks»**.

---

## 1. Navegación

Selector de sección fijo arriba del sidebar: **📍 Ubicaciones** | **🎯 Radar**.
Comunes (siempre visibles): **Inicio** (centro de mando) y grupo **Sistema**
(Sistema · Configuración · Asistente IA). Cada sección muestra SOLO sus
pantallas: menos menú, menos clicks, cero pantallas huérfanas.

| Sección 1 · Ubicaciones (Sabueso) | Sección 2 · Radar (repo Biokool) |
|---|---|
| Analizar (puerta única) | Panel Radar |
| Reporte | Operación |
| Mapa | Leads |
| Comparador | Mapa Radar (mismo Mapa, preset Radar) |
| Historial | Sistema (tarjetas Radar) |
| Aprende | Geofencing · Exportación |

## 2. Sección 1 — Ubicaciones (cerrar las 53 funciones del inventario)

**Flujo rey (2 campos + 1 clic, como Sabueso):** página `Analizar` con giro
(autocompletado + confirmación del mapeo giro→SCIAN editable) y dirección o
link de Google Maps → geocoding REAL → pin confirmable en minimapa sin salir
del flujo → «Analizar» → el **Reporte** completo en una pantalla.

### Backend
1. **Geocoding real** (`territories.py`): parser de links de Maps
   (`@lat,lon`, `!3d/!4d`, `?q=`, place) + resolución de links cortos
   (seguir redirect) + geocodificación de direcciones con **Nominatim/OSM**
   (sin llave; error honesto si no resuelve) + **reverse** para la etiqueta
   legible (colonia, municipio, entidad). Se acaba el stub del Zócalo.
2. **Contexto completo del reporte** (`build_report_context`): agregar desde
   `prod.inegi_agebs` y DENUE y pasar TODAS las claves al builder:
   población total y por edad/sexo (0–14, 15–29, 30–59, 60+), hogares
   (viviendas, ocupantes), PEA ocupada, **NSE predominante** (banda AGEB,
   etiqueta «Perfil de gasto detectado» + referencia AMAI 2024), entorno
   (total + 9 categorías con top-3 ejemplos), competencia **lista** (nombre,
   distancia, «PARECE ACTIVO», diferencial anillo 1–2 km), **atractores**
   ordenados por distancia con link a Maps.
3. **Catálogo de 9 categorías** (rangos SCIAN) reutilizable: atractores,
   mapa de atractores, dona y acordeones del entorno.
4. **Negocios ancla**: catálogo `anchor_weights` (farmacias de descuento,
   supermercados, bancos, etc., con peso y radio) + detección + **efecto
   ancla en Huff** `A_j' = A_j × (1 + Σ w_a)`.
5. **Isócronas reales**: conector Valhalla (`VALHALLA_BASE_URL`, default el
   demo público) → polígonos 5 min caminando / 10 moto / 15 auto +
   población y competidores por isócrona. Si el servicio cae → radios
   etiquetados como radios (honestidad intacta).
6. **Vialidades + movilidad**: Overpass/OSM para vías principales cercanas
   (distancia y tiempo en auto vía routing) + **proxies §3.10** vehicular y
   peatonal (rangos + nivel /100, siempre etiquetados «estimado»).
7. **Catálogo sectorial por giro** (`cat_sector_data`): ticket, hora pico,
   % delivery, top productos, fuente; **fichas de los 15 giros frecuentes**
   del Anexo B.4 (SCIAN múltiples, editorial, supuestos TAM editables,
   plantilla de break-even). El bloque de delivery se muestra solo si el
   giro lo soporta. El **perfil editorial** puede redactarlo el operador IA
   y se cachea en `knowledge_facts`.
8. **Compartir**: tokens de invitado (`report_shares`, expirables/revocables)
   + ruta pública `/r/{token}` de solo lectura; botón WhatsApp (`wa.me` con
   resumen + link); botón «PDF» = vista imprimible del reporte (CSS print,
   «Guardar como PDF» del navegador) servida en `/reporte/{id}/imprimir`.
9. **Comparador sin fricción**: acepta direcciones directas (crea la
   investigación y la deja en Historial, declarado), límite **6**, y la
   **ganadora persiste** (`es_principal`).
10. **Modo inmobiliario**: investigación `real_estate` → el reporte prioriza
    entorno por grupos + anclas + vialidades y omite bloques operativos.
11. **Aprende**: 4 explicadores (competencia, movimiento, población,
    actividad comercial) enlazados desde cada bloque con «¿qué es esto?».

### Frontend — Reporte profesional (la pantalla lo es todo)
Cabecera con veredicto grande + botones WhatsApp / PDF / Link invitado.
Cuerpo con **elementos visuales reales**: mapa Leaflet embebido con
marcadores numerados por anillo y leyenda; mapa de atractores con chips de
las 9 categorías; mapa de isócronas con zoom por modo; **dona ECharts** del
entorno; acordeones por categoría con ejemplos; listas numeradas con
distancia y botón Maps; tarjetas por segmento de edad; sellos («PARECE
ACTIVO», «PERFIL DE GASTO DETECTADO», nivel de movilidad /100); tablas de
alcance por isócrona; **calculadoras interactivas** de renta (precio/m² ×
superficie) y punto de equilibrio (estructura de costos editable).

### Excepciones declaradas (no son humo, son decisiones del propio SRS)
- Paquetes/pagos (#48): fuera del núcleo open source (SRS NR-06). Sin módulo
  de cobro; el conteo de análisis queda en Historial.
- Conectores Google Places/TomTom/SCINCE (#45): el núcleo opera con
  INEGI + OSM (regla CON-01); quedan como conectores opcionales con stub
  honesto, no bloquean nada.
- API keys por usuario y webhooks (#49): fase 2; la API ya es el flujo
  conectable y la sync CRM vive en la Sección 2.

## 3. Sección 2 — Radar (las 102 funciones + R1–R17)

### Páginas
- **Panel Radar**: réplica funcional del Panel original dentro de la sección:
  4 alertas, 4 KPIs, 4 gráficas (embudo, score, actividad, líneas), con los
  datos reales de la API actual.
- **Operación**: las 5 etapas con gating y bloqueo por orden (409
  diferenciado), providers con coherencia (scraper/enrichment/crm),
  bitácora de corridas, tarjetas LinkedIn (conectar/estado/stats) y clima.
- **Leads**: la lista única actual + drawer completo del original («Cómo
  contactarlo» con Llamar/WhatsApp/LinkedIn/Maps, stepper de 6 etapas,
  notas, registrar señal, `whyLinea`, badges Apollo/CRM) y los **filtros
  geográficos nuevos** (abajo).
- **Mapa Radar**: mismo Mapa con preset `?modo=radar` (capa de leads y capa
  térmica activas, panel de filtros geográficos visible).
- **Sistema**: las 5 tarjetas del original (salud, providers, workflows,
  LinkedIn, config) integradas en la página Sistema actual.

### Filtros entidad / municipio / colonia / CP / SCIAN (no existen en el repo: se derivan)
1. Migración **0005**: columnas `entidad, municipio, colonia, cp, scian` en
   `prod.leads` (nullable, con índices).
2. `POST /leads/enrich-geo`: para leads con geometría → join espacial con
   AGEBs (entidad/municipio por contención) + establecimiento DENUE más
   cercano ≤500 m (colonia, CP, SCIAN); para leads sin geometría → regex de
   CP (5 dígitos) sobre la dirección. Reporta actualizados/pendientes.
   Botón en Operación («Enriquecer geografía») y nodo HTTP opcional en el
   workflow 02 tras el scoring.
3. `GET /catalogs/geo-filters`: valores disponibles con cascada
   (entidad → municipios → colonias → CP) y lista SCIAN, desde leads y
   desde establecimientos.
4. El listado de leads, el conteo y el endpoint geo del mapa aceptan los 5
   filtros. Los establecimientos DENUE ya traen los campos: mismos filtros
   en su capa del mapa.
5. Fiel al repo: se conservan las sutilezas documentadas (la señal suma +25
   y regresa la etapa a `nuevo`; las señales de `input.json` se re-aplican
   en cada corrida 03) — están en el inventario §2.3/§3 y no se «corrigen»
   en silencio.

## 4. Validación de trazabilidad (cierre obligatorio)
- Tabla final en este documento o en `docs/REVISION-2-SECCIONES.md`: cada
  fila de ambos inventarios → dónde vive ahora o excepción declarada.
- `pytest` verde (97 previos + nuevos), `npm run build` verde, contrato
  frontend↔API con 0 huérfanas, recorrido por las páginas de ambas
  secciones con datos de prueba (incluye: geocoding de un link de Maps con
  coordenadas, reporte con las 14 secciones pobladas, filtros geográficos
  que reducen la lista).
