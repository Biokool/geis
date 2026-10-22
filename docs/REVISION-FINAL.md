# REVISIÓN FINAL — Ecosistema GEIS × Biokool Radar

**Fecha:** 19 de octubre de 2026
**Alcance:** auditoría completa de backend, frontend, datos, documentación e infraestructura del repositorio `~/workspace/geis/`, con corrección de todos los hallazgos. Tres auditores en paralelo (backend, UI/UX, documental) + verificación independiente del coordinador.

**Veredictos globales:**
- `pytest backend/tests -q` → **68/68 passed** (29 originales + 39 nuevos de las fases de fusión y revisión)
- `npm run build` (tsc + vite) → **verde, 0 errores de tipos**
- `docker-compose.yml` → válido (7 servicios)
- `python3 -m py_compile` (todo `backend/`) → OK

---

## 1. Alcance revisado

| Frente | Elementos auditados |
|---|---|
| Backend | 6 módulos en `app/analytics/` (ism, huff, tam, idt, scoring, scoring_unificado), 15 routers en `app/api/v1/` (+ `integrations/linkedin.py`), `app/reports/builder.py` (14 secciones), `app/seed.py`, migraciones Alembic 0001→0002, `.env.example`, contratos API↔frontend |
| Frontend | 12 páginas (`Inicio` nueva + las 11 existentes), 67 componentes en `src/components/ui/`, `src/lib/api.ts`, layout Sidebar/Topbar, ThemeToggle, responsive, accesibilidad básica |
| Datos | DDL 0002 (`prod.leads`, `stg.leads_raw`, `prod.runs`, `prod.providers`, `prod.proposals`, `prod.warm_signals`, `prod.linkedin_stats`), backfill `investigation_leads`→`leads`, seed idempotente |
| Docs/Infra | `README.md`, `docs/ECOSISTEMA-FUSION.md`, `docker-compose.yml` (7 servicios, perfiles `automation`/`tunnel`), 5 workflows n8n, `scraper/`, `signals/`, `Makefile` |

---

## 2. Trazabilidad finalidad → resultado esperado → output verificado

| # | Módulo | Finalidad | Resultado esperado | Output verificado | Comprobación |
|---|---|---|---|---|---|
| 1 | Motor analítico (ISM/Huff/TAM/IDT) | Cuantificar oportunidad territorial con fórmulas auditables | ISM=D/(O+1) con bandas; Huff con rango λ±0.5; TAM con rango ±25%; IDT 0–100 | Funciones puras + 20 tests nuevos (bordes, fuzz 200 casos, 12 meses) | `pytest` 68/68 |
| 2 | Score unificado | Priorizar cuentas con lo espacial + lo conductual | Score ∈ [0,100], pesos suman 1 (0.65+0.35), componentes explicables, vertical inválida → error | `scoring_unificado.py` validado; `score_components` en JSONB | `pytest` + lectura |
| 3 | Reporte 14 secciones | Entregable de decisión sin placeholders | 13 secciones SRS + §14 plan de contacto, valores calculados, "dato no disponible" donde falte | `builder.py` genera 14 secciones; sin "lorem" | lectura + test |
| 4 | Leads unificada + pipeline | Una sola tabla de leads con etapa comercial | `prod.leads` (source, geom, etapa 6 estados, UNIQUE 3 cols), backfill desde investigation_leads | Migración 0002 + seed idempotente | lectura DDL/seed |
| 5 | Pipelines 01–05 + ETL | Orquestación con bloqueo por orden | `POST /pipelines/run/{stage}` rechaza 409 con motivo si la previa no está OK | Router + página Operación | lectura código |
| 6 | Providers anti-cautiverio | Conmutar local/cloud sin reescribir | 8 providers en `prod.providers`, `GET/PUT /providers` | Seed + router + página Sistema | lectura código |
| 7 | Scraper | Provider `scraper` de lugares | API `:5000/scrape` + `/health`, modo Playwright/Apify | `scraper/` + healthcheck en compose | lectura + compose |
| 8 | Señales + LinkedIn | Señales cálidas al score | `POST /signals` → warm_signals; OAuth parametrizado (501 sin credenciales) | Routers + `signals/input.json` válido | lectura código |
| 9 | Proposals | Propuestas por lead (fase 2) | CRUD `POST/GET /proposals` | Router nuevo | lectura código |
| 10 | UI Mapa | Territorio visual con capas honestas | Pines por estrato/línea, heatmap, capa térmica, leyenda, tooltips, atribución | `Mapa.tsx` reescrito en partes | lectura + build |
| 11 | UI Reporte | Las 14 secciones legibles | Acordeón ordenado, veredicto con factores, insignias "estimado", advertencias | `Reporte.tsx` reescrito al contrato real | lectura + build |
| 12 | UI Operación/Sistema | Control y gobierno | Pipeline con ▶ y bloqueo visible; semáforo de salud; providers conmutables | Páginas nuevas | lectura + build |
| 13 | UI Inicio | Portada del ecosistema | Qué es, 3 flujos, estado del sistema | `Inicio.tsx` nueva, ruta `/` | lectura + build |
| 14 | Exportación | Sacar leads del sistema | CSV real (tope 5,000, `denue_id` llave); Excel → 501 honesto | `POST /leads/export` + `filas_a_csv()` testeada | `pytest` + lectura |

---

## 3. Fórmulas verificadas

| Fórmula | Archivo | Checks aplicados | Estado |
|---|---|---|---|
| ISM = D/(O+1), bandas P10/P50/P90 | `analytics/ism.py` | O=0 → D (Laplace); D,O ≥ 0; bandas por benchmark | ✅ |
| Huff P_ij, Demanda_j, rango λ±0.5 | `analytics/huff.py` | denominador 0 → 0.0; D_ij=0 → ValueError; salida como rango | ✅ |
| TAM = P·G·F_nse·F_pen, rango ±25% | `analytics/tam.py` | Captura_j = TAM·(Demanda_j/ΣD); advertencia "no son ventas" | ✅ |
| IDT = 100·(0.35E+0.30I+0.20T+0.15A) | `analytics/idt.py` | pesos suman 1 (assert); componentes 0–1; faltante → neutro marcado | ✅ |
| Score B2B = 100·Σwx/Σw | `analytics/scoring.py` | **FIX:** valida pesos no-negativos y Σw>0 (antes: negativos o Σw=0 rompían [0,100]) | ✅ corregido |
| Score unificado (0.30/0.12/0.10/0.08/0.05 + 0.15/0.15/0.05 = 1.00) | `analytics/scoring_unificado.py` | **FIX:** vertical desconocida → ValueError (antes caía a biokool en silencio); fuzz 200 casos ∈ [0,100] | ✅ corregido |
| linea_recomendada(mes, giro) | `analytics/scoring_unificado.py` | **FIX:** mes ∉ 1–12 → ValueError; verificado 12/12 meses sin huecos | ✅ corregido |
| Renta = precio/m² × m²; equilibrio vs renta; efecto ancla | `sugerir_plan_contacto()` (nuevo) | giro=None → "dato no disponible"; regex de giro sincronizada front/back | ✅ nuevo |
| NSE proxy (bandas), KDE, isócronas | analytics + geo | documentados; isócronas vía provider (fase 2: OSRM propio) | ✅ |

---

## 4. Hallazgos y fixes aplicados

### Backend (13)

| # | Sev. | Archivo | Descripción | Fix |
|---|---|---|---|---|
| B1 | Alta | `reports/builder.py` | Faltaba la §14 `plan_contacto` del blueprint | Nueva `sugerir_plan_contacto()` + sección en el builder |
| B2 | Alta | `reports/builder.py:93` | Placeholder quemado en `perfil_cliente.editorial` | Sin editorial → `{"estado": "dato no disponible"}` |
| B3 | Alta | `api/v1/leads.py` | `POST /leads/export` → 404 | Endpoint CSV real (tope 5,000; excel → 501; `filas_a_csv()` testeada) |
| B4 | Alta | — | `GET /reports/{id}/pdf` y `POST /leads/sync` no existen | Declarados Fase 2; UI los deshabilita con tooltip honesto |
| B5 | Media | `api.ts` vs `geo_weather.py` | Frontend leía `temp_c`; backend devuelve `temperature_c` | Corregido a `temperature_c` |
| B6 | Media | `Reporte.tsx` vs backend | Regex de giro para "solar" divergía (plaza → solar en front, evaporativa en back) | Regex sincronizado + comentario anti-divergencia |
| B7 | Media | `api/v1/territories.py` | Stub `from-polygon` sin uso real | Revertido; Geofencing opera en sesión con nota honesta |
| B8 | Media | `analytics/scoring.py` | Pesos sin validar (negativos/Σw=0) | Validación no-negativos y Σw>0 |
| B9 | Media | `analytics/scoring_unificado.py` | Vertical desconocida → biokool silencioso | `ValueError` |
| B10 | Media | `analytics/scoring_unificado.py` | `linea_recomendada` aceptaba mes inválido | `ValueError`; 12/12 meses OK |
| B11 | Media | `.env.example` | Faltaban 6 vars leídas por el código | Agregadas (LINKEDIN_ACCESS_TOKEN, MODEL_VERSION, etc.) |
| B12 | Baja | varios | 7 imports muertos | Eliminados (pyflakes limpio) |
| B13 | Baja | `seed.py` | venv en `/tmp` imposible (tmpfs lleno) | venv en `~/workspace/.venv-rev` (documentado) |

### Frontend (14)

| # | Sev. | Archivo | Descripción | Fix |
|---|---|---|---|---|
| F1 | Crítica | `pages/Reporte.tsx` | Llamaba `POST /analysis/location` esperando `secciones[]` (ese endpoint no las devuelve) | Reescrito contra `POST /reports` (13 secciones + veredicto + §14) |
| F2 | Crítica | `pages/Reporte.tsx` | Modo dirección enviaba `{giro, direccion}` → 422 | Geocode primero (`/territories/geocode`), luego reporte |
| F3 | Crítica | `pages/Mapa.tsx` | `b2b-prospecting` con `{territory_type:'polygon'}` → 422 | Centroide + radio equivalente del polígono |
| F4 | Crítica | `pages/Historial.tsx` | Campos inexistentes (`id`, `nombre`) → crash; `rerun`/`DELETE` → 404 | Alineado al schema real; re-ejecutar = clonar; Eliminar deshabilitado Fase 2 |
| F5 | Crítica | `pages/Geofencing.tsx` | `POST /territories/from-polygon` → 404 | Territorio en sesión (zustand) + nota honesta + advertencia "Población ≠ compradores" |
| F6 | Crítica | `pages/Exportacion.tsx` | `POST /leads/export`, `/leads/sync` → 404; `api()` corrompería binarios | Deshabilitados con tooltip; nuevo `apiBlob()` para el futuro |
| F7 | Media | (nueva) | Sin portada | `pages/Inicio.tsx` (ruta `/`, 3 flujos, estado del sistema) |
| F8 | Media | layout | Sidebar fijo sin colapso móvil; asides rígidos; tablas sin scroll-x | Drawer móvil (Sheet), `flex-col` + `55vh` en móvil, `overflow-x-auto` |
| F9 | Media | varios | `window.location.assign` (recarga completa) | `useNavigate` |
| F10 | Media | `pages/Sistema.tsx` | `health.providers` como dicts → todo "Desconocido" | `estadoProvider()` extrae modo/estado real |
| F11 | Media | toda la app | Cero insignias "estimado" | Nuevo `ui/Estimado.tsx` (`EstimadoBadge`); advertencias del backend como Alerts |
| F12 | Baja | `ui/DataTable.tsx` | Búsqueda sin `aria-label` | Añadido |
| F13 | Baja | `layout/Topbar.tsx` | Bloque duplicado | Reescrito limpio |
| F14 | Baja | `App.tsx` | Catch-all → `/mapa` | → `/` (Inicio) |

### Documental / infra (5)

| # | Sev. | Archivo | Descripción | Fix |
|---|---|---|---|---|
| D1 | Alta | `README.md` | Quickstart `up → seed` omitía migraciones (el seed inserta en tablas 0002) | Quickstart: `up → make migrate → make seed`; nuevo target `migrate` en Makefile |
| D2 | Media | `docker-compose.yml` | Scraper sin healthcheck | Agregado (urllib; la imagen no garantiza curl) |
| D3 | Media | `docs/ECOSISTEMA-FUSION.md` | Provider llamado `places`; eran 6 providers listados | Nombre real `scraper`; 8 providers; estado → implementado |
| D4 | Media | `docs/ECOSISTEMA-FUSION.md` | §6/§7 sin `POST /leads/export`, sin página Inicio, sin nota Fase 2 (pdf/sync/delete) | Actualizado en esta revisión |
| D5 | Baja | `scraper/README.md` | Nombre de provider incorrecto | Corregido a `scraper` |

**Conteo:** 32 hallazgos (7 críticos, 14 altos/medios, 11 bajos/menores). **Todos corregidos o declarados Fase 2 con UI honesta.**

---

## 5. Mejoras UI/UX aplicadas (top)

1. **Reporte reescrito al contrato real** — el recorrido crítico (Operación → Leads → Reporte → Exportación) ahora funciona de punta a punta contra la API.
2. **Cero botones muertos** — todo lo no implementado está deshabilitado con Tooltip que explica por qué y qué falta (patrón `BotonPendiente`), en vez de 404 silenciosos.
3. **Sello de honestidad** — `EstimadoBadge` + advertencias del backend ("población ≠ compradores", "etiqueta simplificada, no oficial AMAI", "isócrona ≠ clientes") visibles donde el SRS las exige.
4. **Portada + responsive móvil** — `Inicio.tsx` orienta; Sidebar en drawer; mapas y tablas usables en pantallas chicas.
5. **Drawer "Cómo contactarlo"** — Llamar (`tel:`), WhatsApp (`wa.me` con normalización MX a 10 dígitos), abrir sitio, buscar en LinkedIn; si falta un dato dice cuál y por qué no puede obtenerse solo.

---

## 6. Pendientes honestos (requieren Docker, credenciales reales o navegador en la máquina de Chino)

1. **`docker compose up --build -d`** en local (la VM no tiene bridge networking) → luego `make migrate`, `make seed`, abrir http://localhost:3000 y http://localhost:8000/docs.
2. **Migración 0002 + seed contra PostGIS real**, incluida la 2ª corrida del seed (idempotencia verificada por lectura, no por ejecución).
3. **Smoke test API↔frontend con stack vivo** (contratos validados por lectura de routers+schemas, no por ejecución).
4. **Importar los 5 workflows a n8n** y re-enlazar credenciales (Postgres "radar", Apollo, HubSpot); si un nodo intermedio falla, el run queda en `running` (mejora futura: error-workflow con PATCH).
5. **LinkedIn OAuth** — requiere app real con Community Management API (sin credenciales → 501 documentado).
6. **Fase 2 backend:** `GET /reports/{id}/pdf`, `POST /leads/sync`, `DELETE /investigations/{id}`, motor de isócronas propio (OSRM/Valhalla).
7. **Verificación visual** (móvil/desktop, dark mode en Leaflet/ECharts, contraste real) — sin navegador disponible en este entorno.
8. n8n y cloudflared sin healthcheck confirmado (binarios de sus imágenes no verificables sin Docker).

---

*Fin de la revisión final — 19 de octubre de 2026. Coordinador: revisión ejecutada con 3 auditores en paralelo; verificación independiente: pytest 68/68, tsc+vite build verde, compose YAML válido, py_compile OK.*
