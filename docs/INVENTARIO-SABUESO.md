# Inventario exhaustivo — Sabueso IA vs. GEIS actual (Sección 1)

> **Encargo:** la nueva Sección 1 del sistema debe tener «todas y sin excepción» las
> funciones de Sabueso IA (plataforma + videos + Instagram). Este documento mapea
> cada capacidad de Sabueso contra el código real de `~/workspace/geis-github/`
> (auditado archivo por archivo el 2026-10-21).
>
> **Fuentes Sabueso:** SRS `GEIS-SRS.md` §1.2.1 (landing verificada), §1.2.2
> (reporte de ejemplo inspeccionado en vivo), §1.2.3, §2.4, §3.9–§3.12,
> Anexo B (Instagram @ernestomarcardenas, 93 reels).
>
> **Hallazgo central:** el *builder* del reporte (`backend/app/reports/builder.py`)
> ya compone las 14 secciones, pero `POST /reports`
> (`backend/app/api/v1/reports.py::generar_reporte`) solo le pasa anillos, TAM,
> Huff, supuestos y ediciones. Las claves `demanda`, `hogares`, `atractores`,
> `competencia_lista`, `entorno`, `isocronas`, `vialidades`, `movilidad`,
> `nse_etiqueta` y `perfil_editorial` **nunca se calculan ni se pasan**: un
> reporte real salen **9 secciones vacías**. La buena noticia: casi todos los
> datos ya existen en `prod.inegi_agebs` y `prod.denue_establishments`.

**Resumen:** 53 funciones — ✅ 6 · ⚠️ 20 · ❌ 27.

---

## Tabla maestra

| # | Función Sabueso | Fuente | Estado en GEIS | Qué falta exactamente |
|---|---|---|---|---|
| 1 | Escribir el **giro** en texto libre y resolverlo a actividad | SRS §1.2.1 paso 1; §1.8 | ⚠️ Parcial — `POST /reports` y `POST /analysis/location` aceptan `giro`; `analysis.py::resolver_scian` busca en `cat_giro_scian` (ILIKE) y si no hay mapeo cae a la clase genérica `722515` con advertencia | Autocompletado de giros en el form; **confirmación/edición del mapeo giro→SCIAN antes de calcular** (RN-SUC-03); entrada rápida desde Inicio (hoy hay que ir a la página Reporte) |
| 2 | Pegar una **dirección** en texto libre y geocodificarla | SRS §1.2.1 paso 2 | ❌ No existe — `POST /territories/geocode` (`territories.py`) con `address` devuelve **siempre el Zócalo CDMX** con `stub: true` | Conector de geocoding real (Nominatim/OSM o Google) en `territories.py`; manejo de error si la dirección no resuelve |
| 3 | Pegar un **link de Google Maps** y extraer el punto | SRS §1.2.1 paso 2 | ❌ No existe — el schema `GeocodeRequest` menciona "link de Maps" en la descripción, pero nadie parsea URLs ni resuelve links cortos (goo.gl/maps.app) | Parser de links (coordenadas en URL `@lat,lon`, `?q=`, place-id) + resolución de links cortos antes del geocode |
| 4 | **Confirmación visual del punto** en el mapa antes de calcular | SRS §1.4.3, RF-004 | ⚠️ Parcial — `Mapa.tsx` permite crear investigación desde un establecimiento o polígono, pero el flujo de Reporte no muestra mapa de confirmación; el modo por defecto del form es **Lat/Lon** (el usuario debe conocer coordenadas) | Mapa embebido de confirmación con pin arrastrable en el paso 2 del flujo; modo «Dirección» como default |
| 5 | **Radios de análisis 1 km y 2 km** | SRS §1.2.2 | ✅ Existe — `ReportCreate.radios = [1000, 2000]`; `compute_location_analysis` calcula por anillos | — (matiz en #17) |
| 6 | Cabecera «REPORTE DE UBICACIÓN / Análisis para {giro}» con ubicación, fecha y radios | SRS §1.2.2 §1 | ⚠️ Parcial — `builder.cabecera` + render en `Reporte.tsx` existen | La `etiqueta_ubicacion` es **«lat, lon» crudo** (`reports.py`); falta geocodificación inversa → colonia/municipio/entidad legibles |
| 7 | Botón **Compartir por WhatsApp** en la cabecera del reporte | SRS §1.2.2 §1; Anexo B.3.7 | ❌ No existe — el único `wa.me` del sistema está en `Leads.tsx` (contactar un lead, Sección 2) | Deep link `wa.me/?text=` con resumen del veredicto + link del reporte en la cabecera de `Reporte.tsx` |
| 8 | Botón **Guardar PDF** del reporte | SRS §1.2.2 §1; planes | ❌ No existe — `Exportacion.tsx` lo muestra como `BotonPendiente` honesto: "aún no existe el endpoint GET /reports/{id}/pdf" | Endpoint `GET /reports/{id}/pdf` (render del payload persistido) + botón en cabecera del reporte |
| 9 | **Link compartible con modo invitado** (`?id={uuid}&compartido=1&guest=1`) | SRS §1.2.2 §1; RF-019 | ❌ No existe — no hay tokens de compartir, ni vista pública de solo lectura; `user_id` default "guest" es solo una etiqueta | Tokens opacos expirables/revocables + ruta pública `/r/{token}` que renderice el payload sin login |
| 10 | § **Perfil del cliente** (texto editorial del giro) | SRS §1.2.2 §2 | ⚠️ Parcial — el builder acepta `perfil_editorial` y si falta declara "dato no disponible" (honesto), pero `reports.py` **nunca lo pasa** → la sección siempre sale vacía | Catálogo editorial por giro **o** conectar la herramienta `report_section` del operador IA (`app/ai/operator.py`, ya existe) para redactarlo y cachearlo en `knowledge_facts` |
| 11 | § **Clientes y resultado de la zona**: tarjetas por segmento con población del segmento | SRS §1.2.2 §3 | ⚠️ Parcial — `builder.clientes_zona` existe; `reports.py` no pasa `demanda` → `segmentos: []`, `poblacion_total: null` | Agregación AGEB→ctx en `generar_reporte`: sumar `pob_total`, `pob_30_59` etc. de `prod.inegi_agebs` intersectadas (las columnas ya existen; hoy solo se suma `pob_30_59` para el ISM en `demanda_pob_3059`) |
| 12 | **Advertencias de honestidad** («es población de la zona, no una estimación de compradores», «no equivalen a consumidores») | SRS §1.2.2 §3/§9 | ✅ Existe — notas fijas en el builder (`clientes_zona.nota`, `poblacion_viviendas.advertencia`, `nse_nota`, advertencia TAM-03) y badge `EstimadoBadge` en la UI | — |
| 13 | **Datos de mercado del giro** (ticket promedio, hora pico, % delivery, productos top) con fuentes sectoriales citadas (PROFECO, Parrot, Rappi) | SRS §1.2.2 §3; §2.4 | ❌ No existe — no hay catálogo sectorial; `connectors/sector_data/` de §2.4 nunca se creó | Catálogo editable por giro (`cat_sector_data`: ticket, hora pico, % delivery, top productos, fuente) + bloque en el reporte |
| 14 | § **Hogares y familias** (viviendas habitadas, personas por vivienda con el cálculo mostrado) | SRS §1.2.2 §4 | ⚠️ Parcial — `builder.hogares_familias` compone `viv_habitadas`, `prom_ocupantes`, % internet/computadora/automóvil; `reports.py` no pasa `hogares` → todo null | Agregar `viv_habitadas` y `prom_ocupantes_viv` de las AGEB del radio al ctx (columnas existentes en `models/territorio.py::InegiAgeb`) |
| 15 | § **Atractores de tráfico**: lista numerada por cercanía con nombre, distancia y botón «abrir en Maps» | SRS §1.2.2 §5; RF §1.2.3 | ❌ No existe — nadie calcula atractores; el builder deja `atractores_trafico.items: []` siempre | Query DENUE por categorías atractoras con `ST_Distance` ordenado, top-N por radio, + URL de Google Maps por ítem; pasarla como `atractores` al builder |
| 16 | § **Competencia en la zona**: conteo por anillos | SRS §1.2.2 §6 | ✅ Existe — `analysis.py::competencia_por_radio` (misma clase SCIAN, `ST_DWithin`) → `builder.competencia.por_anillo` con ISM y banda por anillo | — (matiz en #17) |
| 17 | § Competencia: **lista con nombre, distancia y estado «PARECE ACTIVO»** + conteo diferencial del anillo 1–2 km | SRS §1.2.2 §6 | ❌ No existe — `competencia.lista` siempre vacía; los conteos son acumulados por radio (≤1, ≤2), Sabueso muestra ≤1 km y el **anillo 1–2 km** por separado | Query de competidores con nombre + `ST_Distance` + estado desde `denue_establishments.is_active` («PARECE ACTIVO»); presentar el diferencial 1–2 km |
| 18 | Mapa 1: **ubicación y negocios cercanos** con marcadores numerados y leyenda por anillo | SRS §1.2.2 §7a | ❌ En el reporte no — `builder.mapas` es solo un **descriptor de nombres de capa** y `Reporte.tsx` lo renderiza como lista de texto mono; `Mapa.tsx` sí pinta marcadores DENUE pero sin numeración por anillo y desconectado del reporte | Mapa Leaflet embebido en la sección Mapas del reporte con marcadores numerados (competencia/atractores) y leyenda por anillo |
| 19 | Mapa 2: **negocios que atraen movimiento por categoría** con filtros (9 categorías: similares, restaurantes/cafés/pastelerías, compras y servicios diarios, hospitales y farmacias, escuelas y universidades, bancos, gimnasios, servicios especializados, plazas y gasolineras) | SRS §1.2.2 §7b | ❌ No existe — no hay catálogo categoría→SCIAN ni capa de atractores en ningún mapa | Catálogo de las 9 categorías (rangos SCIAN) reutilizable por #15/#19/#27 + capa con chips de filtro en Mapa y en el mapa del reporte |
| 20 | Mapa 3: **vialidades cercanas** | SRS §1.2.2 §7c | ❌ No existe — no hay fuente de red vial ingerida (OSM no está en el ETL) | Ingesta ligera de vialidades OSM (Overpass) o capa WMS; sin esto, #32 tampoco es posible |
| 21 | Mapa 4: minimapa **corredor vial** (movilidad vehicular) | SRS §1.2.2 §7d | ❌ No existe | Depende de #20 + proxy vehicular #33 |
| 22 | Mapa 5: minimapa **flujo peatonal estimado** | SRS §1.2.2 §7e | ❌ No existe | Depende del proxy peatonal #34 |
| 23 | Mapa 6: **alcance por tiempo (isócrona real)** 5 min caminando / 10 min moto / 15 min auto, con zoom por modo | SRS §1.2.2 §7f y §11 | ❌ No existe — no hay motor ni conector de ruteo; el builder deja `area_alcance_tiempo.isocronas: []` y el Mapa dibuja **círculos de radio** (etiquetados honestamente como radios, no isócronas) | Conector de routing (OSRM/Valhalla auto-alojados, SRS §2.4) que devuelva polígonos por modo/tiempo y los persista en el payload |
| 24 | **Tabla de mercado alcanzable por isócrona** (distancia y competidores por modo/tiempo) + tabla «Cómo usar este alcance» con recomendaciones operativas | SRS §1.2.2 §11 | ⚠️ Parcial — el builder trae un texto genérico `como_usarla`; no hay tabla por modo ni recomendaciones por modo | Con #23: agregar población y competidores por isócrona y la tabla de recomendaciones (caminando = barrio, moto = delivery, auto = destino) |
| 25 | § **Entorno comercial**: total de negocios hasta 2 km | SRS §1.2.2 §8 | ❌ No existe — `entorno_comercial.total_negocios` siempre `null`; nadie agrega el DENUE por radio para el reporte | Conteo DENUE total en el radio mayor → ctx `entorno` |
| 26 | § Entorno: **gráfica circular (dona)** por categoría | SRS §1.2.2 §8 | ❌ No existe — sin datos (#25) y `Reporte.tsx` no usa ECharts en ninguna sección | Dona ECharts con las 9 categorías (#19) |
| 27 | § Entorno: **acordeones por categoría** con conteos y ejemplos | SRS §1.2.2 §8 | ⚠️ Parcial — el componente `Accordion` existe y se importa en `Reporte.tsx`, pero `categorias: []` siempre | Mismo catálogo y agregación de #19/#25; ejemplos = top-3 nombres por categoría |
| 28 | § **Población y viviendas**: población total del radio | SRS §1.2.2 §9 | ⚠️ Parcial — solo se calcula la población 30–59 (demanda D del ISM); `poblacion_total` nunca llega al payload | Sumar `pob_total` de AGEB intersectadas por anillo (columna existente) |
| 29 | § Población: **desagregación por sexo y grupos de edad** (0–14, 15–29, 30–59, 60+, sin clasificar) | SRS §1.2.2 §9 | ⚠️ Parcial — las columnas existen **exactas** en `inegi_agebs` (`pob_femenina/masculina`, `pob_0_14`, `pob_15_29`, `pob_30_59`, `pob_60_mas`, `pob_sin_clasificar`); `detalle_edad_sexo` nunca se llena | Agregación por anillo → ctx `demanda.detalle_edad_sexo` + barras en la UI |
| 30 | § Movimiento: **actividad económica** (personas ocupadas y % de la población 15+) | SRS §1.2.2 §10a | ⚠️ Parcial — `pea_ocupada` existe en AGEB; `movimiento_acceso.movilidad` siempre `{}` | Agregar `pea_ocupada` y calcular % sobre población 15+ del radio |
| 31 | § **NSE — «Perfil de gasto detectado»** con referencia a la **regla AMAI 2024** y aclaración de etiqueta simplificada | SRS §1.2.2 §10b; §3.9 | ⚠️ Parcial — columnas `nse_score`/`nse_banda` existen y el **seed** las llena, pero el job ETL `censo_ageb.py` las deja como TODO stub ("Calcularías nse_score/nse_banda") y `reports.py` nunca pasa `nse_etiqueta` → la sección sale vacía en reportes reales | (a) Implementar el proxy AMAI §3.9 en el ETL; (b) leer la banda predominante de las AGEB del radio y pasarla al builder |
| 32 | § Movimiento: **vialidades cercanas con distancia y tiempo en auto** | SRS §1.2.2 §10c | ❌ No existe — `movimiento_acceso.vialidades` siempre `[]` | Depende de #20 (red vial) + tiempos del conector de routing (#23) |
| 33 | § **Movilidad vehicular estimada**: rango de vehículos/día + nivel (ej. 65/100) | SRS §1.2.2 §10d; §3.10 | ❌ No existe — los proxies de §3.10 nunca se implementaron (no hay función en `app/analytics/`) | Implementar proxy vehicular §3.10 (red vial + población + atractores) con rangos y etiqueta «estimado» |
| 34 | § **Movilidad peatonal estimada**: rango de personas que pasan caminando | SRS §1.2.2 §10d; §3.10 | ❌ No existe — idem #33 | Implementar proxy peatonal §3.10 |
| 35 | **Bloque operativo de delivery** para giros aplicables (radio inicial 2–3 km, entrega <30–35 min, métricas de la categoría) | SRS §1.2.2 §12 | ❌ No existe | Bloque condicional por giro usando el catálogo sectorial (#13) |
| 36 | § **Fuentes y datos utilizados** (lista nominal citada con el rol de cada fuente) | SRS §1.2.2 §13; §7.5 | ⚠️ Parcial — `builder.fuentes_datos` trae **ediciones reales** de los datos (`edition_labels(db)`), fecha de cálculo y versión de modelo (linaje GEIS, mejor que nada), pero no la lista nominal estilo Sabueso (INEGI · DENUE · Censo 2020 · SCINCE · geocoding · cálculos propios) | Plantilla de fuentes con rol por fuente efectivamente usada en cada reporte |
| 37 | **Veredicto explícito** avanzar / negociar / buscar otra zona con factores | SRS §1.2.2 §14 (brecha de Sabueso); §6.5 | ✅ Existe — y **supera a la referencia** (Sabueso lo promete en la landing pero su reporte no lo emite): `builder.decidir_veredicto` con decisión, confianza y factores; visible en Reporte, Comparador e Historial | — |
| 38 | **ISM** (saturación del giro en el territorio) | SRS §3.1 (formaliza «potencial comercial» de §1.2.1) | ✅ Existe — `app/analytics/ism.py` (`ISM = D/(O+1)`, bandas océano) calculado por anillo y mostrado en §11 del reporte | — |
| 39 | **TAM** del giro en el territorio con rango y supuestos | SRS §3.3; §1.2.1 «potencial comercial» | ⚠️ Parcial — `app/analytics/tam.py` ✅ con rango; pero los supuestos son **fijos por defecto** (`TAM_SUPUESTOS_DEFAULT`: gasto $2,400, f_nse 1.15, f_pen 0.45 "supuesto editable, catálogo sectorial en fase 2") e iguales para todo giro | Supuestos por giro desde el catálogo sectorial (#13) y editables en el form del análisis |
| 40 | **Negocios ancla**: detección y lista con distancia (regla ANC-01) | Anexo B.3.5/B.5; §3.12.3; plan Rastreador | ❌ No existe — no hay catálogo de anclas ni detección en ningún endpoint o reporte | Catálogo `anchor_weights` (cadenas/farmacias de descuento/supermercados/bancos, peso y radio) + query por territorio + bloque en el reporte |
| 41 | **Efecto ancla** como multiplicador de atractividad en Huff | §3.12.3 | ❌ No existe — Huff usa `base_attractiveness` del catálogo SCIAN sin ajuste por anclas cercanas | Aplicar `A_j' = A_j × (1 + Σ w_a)` en `compute_location_analysis` con las anclas de #40 |
| 42 | **Calculadora de renta mensual** = precio/m² × superficie | Anexo B.5; §3.12.1 | ❌ No existe — ni en el reporte ni como herramienta en la UI | Calculadora en el reporte (inputs precio/m² y superficie, precargables por zona en fase 2) |
| 43 | **Calculadora de punto de equilibrio vs. renta** con estructura de costos fijos (nómina, servicios, contador, impuestos, insumos, mantenimiento, imprevistos) | Anexo B.5; §3.12.2 | ❌ No existe | Plantilla editable por giro: costos fijos → ventas de equilibrio = costos / margen; bloque «viabilidad financiera básica» en el reporte |
| 44 | **Casos de uso por giro** listos (cafeterías, sushi, tintorería, tortillería, carnicería, lavandería, barbería, pizzería, matcha, food truck, pollo asado, farmacias, laboratorios clínicos, consultorio dental, franquicias) | Anexo B.4 | ⚠️ Parcial — el mapeo giro→SCIAN es genérico (1 clase por texto, fallback restaurante); no hay fichas por giro | Catálogo curado de giros frecuentes: SCIAN múltiples por giro, editorial (#10), supuestos TAM (#39), plantilla de equilibrio (#43) y datos sectoriales (#13) |
| 45 | Fuentes declaradas por el creador: **Google Places, INEGI, SCINCE, DENUE, TomTom** | Anexo B.3.4; §1.2.3; §2.4 | ⚠️ Parcial — **DENUE ✅** (bulk + `connectors/denue_api.py` con `buscar`/`ficha` y stub honesto); **INEGI Censo ⚠️** (ETL `censo_ageb.py` es stub; solo seed demo); **SCINCE ❌** (sin ruta de ingesta); **Google Places ❌** (sin conector); **TomTom ❌** (sin conector ni proxy de tráfico) | Ingesta censal real (bulk/SCINCE) en el ETL; conectores opcionales Places/TomTom tras la interfaz de §2.4 (el núcleo debe seguir funcionando solo con INEGI+OSM, regla CON-01) |
| 46 | **Comparador de ubicaciones** (planes Cazador = 3, Pro = 6) | SRS §1.2.1 planes; §6.6 | ⚠️ Parcial — `POST /analysis/compare` (2–5 investigaciones) + `Comparador.tsx` con tabla, semáforos y «Elegir ganadora»; **pero** la ganadora es marca local de sesión (no persiste) y comparar exige haber creado antes cada investigación (más pasos que en Sabueso) | Persistir la ganadora (investigación principal); permitir comparar **direcciones directas** sin crear investigaciones previas; subir el límite a 6 |
| 47 | **Vertical inmobiliaria «Rastreador»** (análisis para inmobiliarias y dueños: entorno por grupos, vialidades, negocios ancla) | SRS §1.2.1 plan Rastreador; Anexo B | ❌ No existe como experiencia — `investigation_type = "real_estate"` existe como **valor de enum** en schema/modelo, sin ningún comportamiento diferenciado: ni vista, ni reporte, ni anclas (#40), ni vialidades (#20) | Modo inmobiliario: al crear investigación `real_estate`, el reporte prioriza entorno por grupos + anclas + vialidades y omite bloques de operación del negocio |
| 48 | **Paquetes por análisis** (Explorador $199 / Cazador $499 / Pro $899 / Rastreador $199, MXN IVA incl.) | SRS §1.2.1 modelo comercial | ❌ No existe — sin módulo de paquetes, créditos ni pagos (el SRS NR-06 lo deja **fuera del núcleo open source a propósito**, como extensión comercial) | Decisión de producto: si la Sección 1 debe cobrar por análisis, crear módulo de créditos (conteo de análisis por usuario) sin pagos primero |
| 49 | «**Conectar el agente a tu flujo comercial**» (integración B2B) | SRS §1.2.1; RF-029 | ⚠️ Parcial — la API FastAPI completa existe y es el "flujo" conectable; la sincronización CRM vive en la Sección 2 (Radar). Para la Sección 1 no hay API keys por usuario ni webhooks de "reporte listo" | API keys con scopes + webhook al terminar un reporte (fase 2) |
| 50 | Contenido pedagógico «**Aprende**» (competencia, movimiento, población, actividad comercial) | SRS §1.2.1 variables pedagógicas | ❌ No existe en la app — el conocimiento está en documentos (SRS/Anexo A), no en una sección de aprendizaje dentro del producto | Sección «Aprende» con 4 explicadores cortos enlazados desde cada bloque del reporte («¿qué es esto?») |
| 51 | **Historial de análisis** del usuario (volver a abrir reportes) | Implícito en planes (análisis comprados reutilizables); SRS §7.1 | ✅ Existe — `Historial.tsx` + `GET /investigations` + reportes persistidos (`GET /reports/{id}`), con reabrir en Mapa/Reporte, comparar y borrar | — |
| 52 | **Mapa interactivo principal** con capas conmutables y conteos | SRS §1.2.1 (mapas interactivos en todos los planes) | ⚠️ Parcial — `Mapa.tsx`: capas DENUE, leads (color por score), calor IDT (círculos), temperatura y líneas Radar, leyenda y popups con acciones ✅; **faltan** las capas que el reporte de Sabueso presume: atractores por categoría (#19), isócronas (#23), vialidades (#20) y AGEB/demografía | Agregar las 3 capas faltantes cuando existan sus datos (#19/#20/#23) |
| 53 | **Densidad de competencia / mapa de calor del giro** | SRS §3.6; §1.2.1 «competencia» | ⚠️ Parcial — la "capa de calor" del Mapa colorea círculos por **IDT** (prospección B2B), no hay superficie KDE de densidad de competencia del giro | Función KDE (§3.6) sobre establecimientos del giro → capa de calor real en Mapa |

---

## Flujo de uso de Sabueso (y el contraste con GEIS hoy)

### Sabueso IA — del clic al reporte

| Paso | Acción del usuario | Interacciones |
|---|---|---|
| 0 | (Solo la primera vez) elegir paquete y pagar: Explorador/Cazador/Pro/Rastreador | fuera del flujo de análisis |
| 1 | **Escribir el tipo de negocio** (1 campo de texto) | 1 campo |
| 2 | **Pegar la dirección o el link de Google Maps** (1 campo) | 1 campo |
| 3 | Enviar → el agente genera el análisis | 1 clic |
| 4 | **Reporte completo en una sola página**: 13 secciones, 6 mapas, gráficas y listas, con los botones **WhatsApp** y **PDF** en la cabecera | 0 clics más |
| 5 | Compartir por WhatsApp o descargar PDF | 1 clic |

**Total: 2 campos + 1 clic para el reporte; 1 clic más para compartirlo.**
El reporte llega además **por WhatsApp** (Anexo B.3.7). No hay cuentas,
dashboards, ni configuración previa: el producto *es* el flujo de 3 pasos.

### GEIS hoy — el mismo resultado

| Ruta | Qué pasa |
|---|---|
| **Reporte.tsx (directa)** | Giro (1 campo) + cambiar a modo «Dirección» (1 clic; el default es **Lat/Lon**) + dirección (1 campo) + «Generar reporte» (1 clic). *Parecen los mismos 3 pasos*, pero el geocode es **stub**: analiza siempre el Zócalo de CDMX, sea cual sea la dirección |
| **Ruta real funcional** | Mapa → ubicar la zona a ojo → clic en un establecimiento o dibujar polígono → «Crear investigación aquí» → ir a Reporte (precargado) → «Generar reporte»: **~3 pantallas y 8–12 interacciones** |
| **Resultado** | De las secciones del payload, **9 salen vacías** (perfil, segmentos, hogares, atractores, lista de competencia, entorno, detalle poblacional, NSE/movimiento, isócronas) y al final **no hay PDF, ni WhatsApp, ni link para compartir** |

### Lección para el diseño («más funciones con menos clicks»)

1. **Un solo formulario de 2 campos** (giro + dirección/link) debe ser la puerta
   de la Sección 1 — con geocoding real (#2/#3) y default en «Dirección».
2. **Confirmación en 1 clic**: pin en minimapa, editable, sin salir del flujo (#4).
3. **El reporte es la pantalla**, no un trámite: todo (mapas, dona, listas,
   calculadoras) se renderiza ahí mismo, y WhatsApp/PDF/link viven en su
   cabecera (#7/#8/#9).
4. Comparar debe aceptar **direcciones nuevas** sin crear investigaciones
   previas (#46).

---

## Elementos visuales del reporte de ejemplo de Sabueso

Del reporte «Análisis para Cafetería» (Roma Norte, CDMX, 28-sep-2026),
inspeccionado en vivo (SRS §1.2.2):

### Mapas (6, Google Maps — atribución «©2026 Google, INEGI»)
- **(a) Ubicación y negocios cercanos** — marcadores **numerados** correlacionados
  con las listas del reporte y **leyenda por anillo** (≤1 km / 1–2 km).
- **(b) Negocios que atraen movimiento por categoría** — con **chips de filtro**
  por las 9 categorías (similares; restaurantes/cafés/pastelerías; compras y
  servicios diarios; hospitales y farmacias; escuelas y universidades; bancos;
  gimnasios; servicios especializados; plazas y gasolineras).
- **(c) Vialidades cercanas.**
- **(d) Minimapa del corredor vial de referencia** (movilidad vehicular).
- **(e) Minimapa de flujo peatonal estimado.**
- **(f) Mapa de alcance por tiempo (isócrona real)** — 5 min caminando (~450 m),
  10 min en moto, 15 min en auto, con **botones de zoom por modo**.

### Gráficas y tablas
- **Gráfica circular (dona)** del entorno comercial por categoría (425 negocios
  a 2 km en el ejemplo).
- **Acordeones por categoría** con conteo y ejemplos (38 similares, 139 compras
  y servicios diarios, 100 restaurantes…, 49 especializados, 44 escuelas,
  22 gimnasios, 22 plazas/gasolineras, 10 bancos).
- **Tabla de mercado alcanzable por isócrona** (tiempo × modo, con distancias y
  conteo de competidores) y **tabla «Cómo usar este alcance»**.
- **Tarjetas por segmento de cliente** (población del segmento, % del grupo
  clave — ej. 13,306 personas de 30–59 años = 52%).
- **Listas numeradas ordenadas por cercanía** (atractores y competencia) con
  nombre, distancia, estado **«PARECE ACTIVO»** y botón para abrir en Maps.

### Etiquetas, sellos y microcopy visual
- Cabecera con etiqueta «REPORTE DE UBICACIÓN», título «Análisis para {giro}» y
  botones **WhatsApp** y **Guardar PDF**.
- Sello de NSE: «PERFIL DE GASTO DETECTADO: Medio a medio alto» (ref. AMAI 2024).
- Sello de movilidad: «RANGO ESTIMADO: 28,000 O MÁS VEHÍCULOS/DÍA» con **nivel
  65/100**; rango peatonal «4,080 a 7,570 personas».
- **Advertencias visibles junto a cada cifra** («Es población de la zona, no una
  estimación de compradores», «no son clientes confirmados», «la etiqueta es
  una estimación simplificada, no una letra AMAI oficial»).
- Sección final «FUENTES Y DATOS UTILIZADOS» con la lista nominal citada.

### Contraste visual en GEIS hoy
`Reporte.tsx` renderiza tarjetas de texto con un renderer genérico
(`RenderContenido`): **sin ningún mapa embebido** (la sección «Mapas» es una
lista de nombres de capa en tipografía mono), **sin dona, sin tablas de
isócrona, sin listas numeradas con distancia**. Los únicos elementos visuales
reales viven en `Mapa.tsx` (Leaflet con capas DENUE/leads/calor IDT/temperatura,
leyenda y popups) y en `Kpis.tsx` (ECharts de estrato y top SCIAN) — ambos
**desconectados del reporte**.
