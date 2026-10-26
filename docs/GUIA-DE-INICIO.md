# GUÍA DE INICIO — GEIS × Biokool Radar

## Qué es este sistema (en una frase)

Una máquina de prospección con inteligencia territorial, dividida en **dos
grandes secciones** (selector arriba del menú): **📍 Ubicaciones** — análisis
de ubicaciones estilo Sabueso IA: giro + dirección → reporte completo — y
**🎯 Radar** — la prospección operativa del repo Biokool: pipeline, leads
puntuados, señales y CRM. **Inicio** y **Sistema** (salud, Configuración,
Asistente IA) son comunes a ambas.

## Arranque técnico (una sola vez)

```bash
cp .env.example .env        # pega tus llaves (DENUE, IA, integraciones)
docker compose up --build -d
make migrate                # alembic upgrade head
make seed                   # datos demo Roma-Condesa (opcional)
```

- Web: http://localhost:3000 · API/docs: http://localhost:8000/docs
- Automatización (opcional): `docker compose --profile automation up -d`
  levanta n8n + scraper; importa los 5 workflows de `n8n/workflows/`.

## Tus primeros 5 pasos (la app te los marca en Inicio)

La página **Inicio** trae la tarjeta «Primeros pasos» con el estado real de
tu instalación y un botón «Siguiente paso». En orden:

1. **Configura tu empresa** (Configuración): elige el giro y llena el perfil
   — manual o con «Llenar con IA» pegando tu URL. Sin perfil, el sistema no
   sabe qué vendes ni a quién buscar.
2. **Carga datos**: con el seed demo o corriendo el pipeline de Operación.
3. **Crea tu primera investigación** (Mapa): dibuja un polígono o haz clic en
   un establecimiento → «Crear investigación aquí». El sistema calcula ISM,
   Huff, TAM e IDT.
4. **Revisa tus leads** (Leads): una sola lista con origen (Espacial/Radar),
   score y ficha con «Cómo contactarlo». Mueve las etapas conforme avances.
5. **Corre el pipeline** (Operación): las 5 etapas en orden; cada corrida
   queda registrada y alimenta Leads y KPIs.

Cuando los 5 están completos, Inicio dice «Sistema operando».

## Cómo avanzar cada semana (la rutina)

- **Lunes — Inteligencia:** revisa el Mapa y el Historial; compara 2–3 zonas
  en el **Comparador** y elige dónde atacar.
- **Diario — Prospección:** trabaja la lista de Leads de mayor a menor score;
  registra el avance de etapa en la ficha.
- **Continuo — Operación:** el pipeline corre por n8n (o manual desde
  Operación); las señales cálidas (LinkedIn, clima) suben el score solas.
- **Viernes — Medición:** KPIs (embudo y distribución de score) y Reporte de
  la zona de la semana para decidir la siguiente.

## Mapa de pantallas

**📍 Sección Ubicaciones (análisis tipo Sabueso)**

| Pantalla | Para qué |
|---|---|
| Analizar | La puerta: giro + dirección o link de Maps → reporte en 1 clic |
| Reporte | Análisis completo visual: mapas, dona, isócronas, calculadoras, compartir (WhatsApp/PDF/link) |
| Mapa | Capas (establecimientos, leads, atractores, isócronas), dibujar zonas |
| Comparador | 2–6 ubicaciones lado a lado (admite direcciones directas), ganadora persistente |
| Historial | Tus investigaciones: reabrir, comparar, borrar |
| Aprende | Qué significa cada bloque del reporte |

**🎯 Sección Radar (prospección tipo Biokool)**

| Pantalla | Para qué |
|---|---|
| Panel Radar | Alertas, KPIs y gráficas del Radar |
| Operación | Pipeline de 5 etapas con orden bloqueado, providers, LinkedIn, clima, enriquecer geografía |
| Leads | Lista única con filtros por entidad, municipio, colonia, CP, SCIAN, etapa y línea; ficha con «Cómo contactarlo» |
| Mapa Radar | El Mapa con preset Radar (leads + capa térmica + filtros geo) |
| Geofencing | Zonas y alertas geográficas |
| Exportación | CSV de leads y reportes |

**Comunes:** Inicio (centro de mando) · Sistema (salud e integraciones) ·
Configuración (perfil de empresa y llaves de IA) · Asistente IA.

## Problemas comunes

- **«No hay datos» en todo:** corre `make seed` o el pipeline (paso 2 y 5).
- **La IA responde 503:** faltan las llaves en `.env` (Configuración, paso 3
  del wizard, genera las líneas exactas).
- **LinkedIn sin conectar:** en Operación/Sistema, botón «Conectar LinkedIn»
  (requiere tu app de LinkedIn Developers).
- **El mapa se ve vacío:** activa las capas (panel de capas del Mapa) y
  verifica que haya establecimientos/leads con coordenadas en tu zona.
