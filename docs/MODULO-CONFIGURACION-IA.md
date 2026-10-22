# Módulo Configuración inicial + IA interna

**Fecha:** 19 de octubre de 2026 · **Estado:** implementado y verificado (82/82 tests)

## 1. Visión

Al arrancar el ecosistema por primera vez, el usuario configura **una sola vez** a qué giro se dedica su empresa mediante un wizard de 4 pasos. El sistema parsea el documento `PERFIL-EMPRESA.md`, deriva automáticamente la **configuración vertical** (pesos de scoring, SCIAN objetivo, parámetros TAM, reglas de línea, canales de contacto, vocabulario) y desde ese momento **todos los cálculos funcionan para ese giro, por especializado que sea**.

Además, el sistema integra **5 API keys de IA** (OpenAI, Anthropic, Gemini, Groq, DeepSeek) detrás de un **operador IA interno** que controla las opciones del sistema vía herramientas: trabaja de forma **híbrida** (datos locales primero; si faltan, usa la IA y guarda el resultado en el conocimiento local) y **auto-aprende** (todo lo investigado alimenta `knowledge_facts` con fuente y confianza).

## 2. El documento PERFIL-EMPRESA.md

Ubicación: `docs/PERFIL-EMPRESA.md` (plantilla) y `docs/PERFIL-EMPRESA.ejemplo-gimnasios.md` (ejemplo lleno: "FitLife Gimnasios").

- **Bloque YAML frontmatter** (entre los dos primeros `---`): es lo que el sistema lee automáticamente. Campos: `empresa` (nombre, sitio_web, ubicacion_base, tamano_empleados, antiguedad_anos), `vertical` (id, giro_descripcion), `productos[]` (nombre, descripcion, ticket_min/max_mxn, ciclo_venta_dias, margen_aprox_pct), `cliente_ideal` (descripcion, tamano, puesto_decisor, dolores), `propuesta_valor`, `diferenciadores[]`, `competidores[]`, `modelo_comercial`, `territorio`, `estacionalidad`, `objetivos[]`, `vocabulario{}`, `scian_sugeridos[]`.
- **Cuerpo markdown** (12 secciones): detalle para humanos; la IA que llena también lo usa como contexto.
- **Dos modos de llenado:** humano (responde `[Tu respuesta aquí]`, o `[PENDIENTE]` si no sabe) o IA ("Llena este perfil con mis materiales. No inventes datos; lo que no encuentres márcalo como `[PENDIENTE]`").

## 3. Parseo y derivación (`backend/app/company/`)

| Archivo | Rol |
|---|---|
| `profile.py` | Parsea el MD: intenta `python-frontmatter`; si devuelve metadata vacía (ocurre cuando hay texto antes del primer `---`, verificado), usa el parser manual (extrae el bloque entre los dos primeros `---` + `yaml.safe_load`). Valida campos críticos (`empresa.nombre`, `vertical.id`, `productos[0]`, `cliente_ideal`, `territorio`) y devuelve la lista de `faltantes`. |
| `schemas.py` | Pydantic v2: `CompanyProfile` (espejo del frontmatter) y `VerticalConfig` (`vertical_id`, `nombre_empresa`, `scian_targets[]`, `demand_intensity{}`, `scoring_weights{8 componentes}`, `tam_defaults[]`, `line_rules[]`, `outreach_channels[]`, `vocabulary{}`, `icp_keywords[]`). |
| `derive.py` | `derive_config(profile) -> VerticalConfig`. Reglas: `scian_sugeridos` → `demand_intensity` 0.8 (0.5 si vacío); pesos = `PESOS_BIOKOOL` si el vertical es climatización, si no `PESOS_GENERICO` con ajustes B2C (detectado por vocabulario: baja peso de estrato/tamaño ×0.5, sube densidad ×1.5 e IDT ×1.25; documentado en `line_rules`); `productos` → `tam_defaults` (ticket = promedio min/max); `dolores` separados por `;` → `icp_keywords`; `canales_contacto` → `outreach_channels`. |
| `store.py` | Perfil activo + caché en memoria de la `VerticalConfig` derivada + `resolve_pesos(vertical_id)`. |

**Tablas** (migración 0003): `company_profiles` (id, vertical_id, nombre, profile_md TEXT, profile_json JSONB, version, is_active, created_at), `knowledge_facts` (id, vertical_id, fact_key, fact_value JSONB, source, confidence 0–1, created_at, updated_at; UNIQUE(vertical_id, fact_key)), `ai_usage_log` (id, provider, purpose, ok, created_at). Migración 0004: relaja el CHECK de `prod.leads.linea_recomendada` para admitir nombres de producto del perfil.

**Endpoints** (`/api/v1/company`): `GET /company/profile` (activo o 404 honesto), `PUT /company/profile` {markdown} → {id, version, faltantes[]} (versiona: desactiva la anterior), `POST /company/profile/derive` {markdown?} → preview sin guardar, `POST /company/profile/activate/{id}`, `GET /company/profiles` (historial).

**Integración con el núcleo:** `score_unificado` usa `scoring_weights` del perfil cuando el `vertical_id` coincide (alias climatización↔biokool); sin perfil, comportamiento idéntico al anterior. El report builder agrega `cabecera.empresa` y bloque `perfil_empresa` (silencioso si no hay perfil). `linea_recomendada(mes, giro, productos_perfil)` devuelve el nombre de producto del perfil si el giro lo menciona.

## 4. IA interna (`backend/app/ai/`)

### 4.1. Proveedores (`providers.py`)

Interfaz común `chat(system, messages) -> str` vía httpx (timeout 60s):

| Provider | Env var | Endpoint / modelo por defecto |
|---|---|---|
| openai | `OPENAI_API_KEY` | `api.openai.com/v1/chat/completions` · `gpt-4o-mini` |
| anthropic | `ANTHROPIC_API_KEY` | `api.anthropic.com/v1/messages` · `claude-3-5-haiku-latest` |
| gemini | `GEMINI_API_KEY` | `generativelanguage.../gemini-2.0-flash:generateContent` |
| groq | `GROQ_API_KEY` | `api.groq.com/openai/v1/chat/completions` · `llama-3.3-70b-versatile` |
| deepseek | `DEEPSEEK_API_KEY` | `api.deepseek.com/chat/completions` · `deepseek-chat` |
| openrouter | `OPENROUTER_API_KEY` (+`OPENROUTER_MODEL`) | `openrouter.ai/api/v1/chat/completions` · `openai/gpt-4o-mini` |
| nvidia | `NVIDIA_API_KEY` (+`NVIDIA_MODEL`) | `integrate.api.nvidia.com/v1/chat/completions` · `meta/llama-3.3-70b-instruct` |
| cloudflare | `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` (+`CLOUDFLARE_MODEL`) | `api.cloudflare.com/.../ai/v1/chat/completions` · `@cf/meta/llama-3.3-70b-instruct-fp8-fast` |

Cadena de fallback en el orden de `AI_DEFAULT_ORDER` (default `openai,anthropic,gemini,groq,deepseek,openrouter,nvidia,cloudflare`). OpenRouter, NVIDIA NIM y Cloudflare Workers AI se consumen vía su endpoint compatible con OpenAI. Si ninguno responde → `AIProviderError` honesto. Las keys viven solo en el servidor (`.env`); el frontend nunca las ve completas.

### 4.2. Conocimiento (`knowledge.py`)

`get_fact(vertical_id, key)`, `save_fact(vertical_id, key, value, source, confidence)` (upsert por UNIQUE), `list_facts(vertical_id)`. Orígenes: `manual`, `system`, `ai:{provider}`.

### 4.3. Operador (`operator.py`)

Herramientas (dicts nombre/descripción/parámetros + ejecutores Python): `company_summary`, `territory_analysis` (lógica interna de análisis de ubicación), `score_lead`, `report_section`, `get_knowledge`, `save_fact`, `suggest_scian` (para giros nuevos).

**Lógica híbrida:** cada herramienta primero consulta local (DB/conocimiento); si no hay dato → llama al primer provider disponible → guarda el resultado en `knowledge_facts` con `source='ai:{provider}'` y `confidence` 0.7. `chat(message, history, vertical_id)`: la IA responde o pide herramienta con formato `TOOL: nombre {json}` (máx 3 rondas); cada uso se registra en `ai_usage_log`.

**Endpoints** (`/api/v1/ai`): `GET /ai/status` → {providers: [{name, configured, last_ok}]}, `POST /ai/chat` {message, history[]} → {reply, tools_used[]}, `POST /ai/fill-profile` {url?, text?, filename?} → {markdown, pendientes[]} con system prompt estricto anti-invención ("no inventes cifras; marca [PENDIENTE]; devuelve SOLO el markdown"). Si hay `url`, descarga el texto (httpx, 20s, máx 30k caracteres).

### 4.4. Auto-aprendizaje

- Lead que pasa a `ganado` (PATCH) → fact `conversion:{giro}` (source `system`, confidence 1.0).
- Reporte generado (POST /reports) → fact `report_insight:{hash_territorio}` con {veredicto, ism}.
- Todo envuelto en try/except: el aprendizaje nunca rompe el flujo principal.

## 5. Frontend

- **`src/pages/Configuracion.tsx`** — wizard en 4 pasos con `ui/Stepper`: (1) **Giro**: 5 cards (Climatización, Gimnasios, Cafeterías/Restaurantes, Talleres, Personalizado→input) que precargan `vertical.id`; (2) **Perfil**: textarea monoespaciada + "Cargar plantilla" / "Cargar ejemplo gimnasios" / "Llenar con IA" (Dialog con tabs URL|texto|archivo → `POST /ai/fill-profile`, muestra `pendientes[]`) + checklist de completitud en vivo (`src/lib/perfil.ts`, parser tolerante sin dependencias); (3) **API keys**: 5 slots con input password + "Probar" (`GET /ai/status`) + "Generar líneas para .env" (Dialog con copiar — honesto: el frontend no escribe el .env); (4) **Resumen**: cards de la VerticalConfig (badges, barras, tabla TAM) + "Guardar y activar" (`PUT /company/profile`, toast, redirect); `faltantes[]` como advertencia con confirmación.
- **`src/pages/Asistente.tsx`** — chat con Message/Bubble, chips `tools_used[]`, estado escribiendo, bienvenida con capacidades, Alert honesto si la IA no está configurada (link a Configuración).
- Sidebar: grupo "Sistema" con Configuración y Asistente IA. Rutas `/configuracion`, `/asistente`. `Inicio.tsx`: banner "Configura tu empresa →" si no hay perfil activo (404); si hay, muestra empresa + vertical + versión.
- `src/lib/api.ts`: 8 funciones tipadas para los nuevos endpoints.

## 6. Variables de entorno

```
OPENAI_API_KEY= ANTHROPIC_API_KEY= GEMINI_API_KEY= GROQ_API_KEY= DEEPSEEK_API_KEY=
AI_DEFAULT_ORDER=openai,anthropic,gemini,groq,deepseek
```

## 7. Verificación

- `pytest backend/tests -q` → **82/82** (68 previos intactos + 14 en `test_company_ai.py`: parseo de plantilla y ejemplo de gimnasios, derive —pesos suman 1, `713940` presente, tickets 799/7990/4800—, knowledge upsert, fallback con mock, operador híbrido con IA mockeada —verifica que guarda el fact y que NO llama a la IA si hay dato local—, `ai_usage_log`, `linea_recomendada` con productos del perfil).
- `npm run build` (tsc + vite) verde. `docker compose config` / YAML válido.

## 8. Pendientes honestos

1. Correr `alembic upgrade head` (0004) contra Postgres real en el primer arranque.
2. Pegar las API keys reales en el `.env` del servidor y reiniciar la API.
3. `POST /ai/fill-profile` con URL: solo extrae texto plano (sin JS); para SPAs, pegar el texto manualmente.
4. El operador usa formato `TOOL:` parseado por regex (no function-calling nativo): suficiente para las 7 herramientas actuales; migrar a tool-calling nativo si se agregan más.
