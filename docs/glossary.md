# GEIS — Glosario

| Término | Definición |
|---|---|
| **GEIS** | GeoEnterprise Intelligence System — plataforma de geomarketing (capa de inteligencia). |
| **Módulo Radar** | Capa de ejecución sobre GEIS: scrapeo, scoring conductual, señales, pipeline comercial, CRM. Adaptación de "Biokool Radar v3". |
| **Biokool** | Empresa cliente/vertical del ejemplo activo: climatización (líneas `koolkat`, `solar`, `evaporativa`). |
| **DENUE** | Directorio Estadístico Nacional de Unidades Económicas (INEGI); fuente oficial de establecimientos. |
| **ISM / Huff / TAM / IDT** | Modelos espaciales de GEIS: índice de saturación de mercado, modelo de gravedad de Huff, Total Addressable Market, índice de demanda territorial. |
| **Lead curado** | Fila de `prod.leads` ya deduplicada, geocodificada y scorada (endpoint `/leads/curados`). |
| **`temp_zona`** | Columna de geocodificación de zona del lead (dirección normalizada → zona/clima). |
| **Señal cálida** | Evento que sube score: manual del SDR, pico de engagement LinkedIn, etc. Tabla `prod.warm_signals`. |
| **Scoring conductual** | Componente del score por comportamiento: temperatura (>30 °C vía Open-Meteo), señales cálidas, engagement LinkedIn. |
| **Línea recomendada** | Producto sugerido por mes según perfil/clima: `koolkat` / `solar` / `evaporativa`. |
| **`stg.leads_raw`** | Landing crudo del scrapeo (paso 01); flag `procesado` lo marca el paso 02. |
| **`prod.runs`** | Bitácora de corridas de pipeline (stage, status, detalle dict). |
| **Gating (bloqueo por orden)** | Regla del backend: un stage no corre si el anterior no terminó OK (HTTP 409). |
| **Provider** | Capacidad externa conmutable (scraper, enrichment, crm, email, weather, linkedin, geocoding, routing) con modos `local`/`cloud`/`disabled`; tabla `prod.providers`. |
| **Regla de oro** | "Los datos aterrizan primero en Postgres; la nube es espejo." |
| **Cursor / `next_cursor`** | Paginación keyset de `/leads*`: se pide `limit≤100` y se sigue el cursor; no existe `total`. |
| **Triple trigger** | Cada workflow n8n arrancable por webhook (API), manual (UI) y CLI (`n8n execute`). |
| **Task Broker (n8n)** | Proceso interno de n8n 2.x que aloja Code nodes; usa un puerto que colisiona al ejecutar CLI dentro del contenedor en marcha (se desvía con `N8N_RUNNERS_BROKER_PORT=5680`). |
| **BOM** | Byte Order Mark (`EF BB BF`) al inicio de archivos UTF-8 de Windows; rompe `JSON.parse` en n8n. |
| **`enriquecido_apollo`** | Flag en `prod.leads`: el lead recibió datos de Apollo (dominio, emails, tamaño, tecnologías). |
| **`crm_synced_at`** | Timestamp del último espejo del lead en HubSpot. |
| **`biokool_etapa/score/linea`** | Propiedades custom de Company en HubSpot creadas para el espejo del pipeline. |
| **Nanoid (workflow id)** | Identificador top-level de cada workflow n8n; permite import upsert idempotente. |
| **Perfil de empresa** | `docs/PERFIL-EMPRESA.md` — documento maestro del giro/negocio que alimenta scoring, TAM y reportes; se edita en el wizard de Configuración. |
