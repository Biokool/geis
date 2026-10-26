# ADR-010 — knowledge_facts vive en public: SQL sin esquema y rollback al tragar errores SQL

- **Estado:** Aceptada (2026-10-26)
- **Ámbito:** `backend/app/reports/context.py`, `backend/app/api/v1/{_common,analysis,reports,leads}.py`, `backend/app/db/session.py` (excepción a AGENTS.md)
- **Relacionadas:** ADR-009 (misma jornada de validación), migración `0003_company_ai.py`, `models/company.py` (docstring del esquema), `sessions/2026-10-26.md`

## Contexto

`POST /api/v1/reports` devolvía **500** con giros de texto libre sin ficha
sectorial (p. ej. pain points pegados en el campo giro). El traceback apuntaba
al `INSERT`/`db.commit()` del reporte (`reports.py`), pero el error real ocurría
antes y en otro lado:

1. `_perfil_editorial` (`context.py`) consultaba
   `FROM prod.knowledge_facts` — tabla que **no existe** en `prod`: la migración
   `0003_company_ai.py` crea `knowledge_facts`/`company_profiles`/
   `ai_usage_log` en el esquema por defecto (`public`), a propósito
   (docstring de `models/company.py`: compatibilidad con SQLite en la suite
   de tests). Era el único SQL crudo del repo que calificaba esas tablas con
   `prod.`.
2. El `except Exception: return None` tragaba el `ProgrammingError` **sin
   rollback** → la sesión quedaba con la transacción abortada (psycopg2
   `InFailedSqlTransaction`).
3. `edition_labels` (`_common.py`) fallaba en cadena (también traga), y el
   `db.commit()` del reporte explotaba con el **error secundario**, lejos de
   la causa. El reporte de las 19:06 pasó porque su giro no llegó a la rama
   editorial (ficha con `editorial` o giro vacío).

## Decisión

1. **SQL editorial sin calificar esquema** (`FROM knowledge_facts`): resuelve
   por `search_path` al esquema por defecto, igual que todo el ORM y que el
   resto de la capa knowledge. No se usa prefijo `public.` para no romper la
   suite SQLite de tests.
2. **`safe_rollback(db)`** (helper nuevo en `app/db/session.py`): todo
   `except` que traga un error **SQL** debe limpiar la sesión o el resto del
   request muere con el error secundario. Best-effort (los fakes de tests no
   implementan `rollback()`). Aplicado en: `context.py` (`_perfil_editorial` +
   competidores por isocrona), `_common.py::edition_labels`,
   `analysis.py::_anclas_cercanas`, `reports.py` y `leads.py`
   (auto-aprendizaje post-commit).
3. **2 tests de regresión** (`test_seccion1.py`): el SQL editorial no lleva
   `prod.` y un fallo SQL tragado deja la sesión limpia (rollback llamado).

## Consecuencias

- ✅ El giro problemático pasa de 500 a **201** (`verdict: "AVANZAR"`, payload
  completo de 14 secciones) y el auto-aprendizaje persiste en
  `public.knowledge_facts` (`report_insight:…`). Segundo POST idéntico → 201
  (sesión no envenenada); `GET /reports/{id}` → 200. **139/139 tests.**
- ✅ Errores futuros de una fuente quedan aislados en su bloque sin envenenar
  el resto del request (fin del patrón causa-1.ª / estallido-2.º).
- ⚠️ Los `except` que no son SQL no tocan sesión (geocoding HTTP, parseo de
  dirección, decode de cursor en leads): quedaron fuera por disciplina.
- ⚠️ Síntomas potenciales del mismo patrón no tocados (fuera de la ruta del
  bug): `investigations.py::db.refresh` y health checks con conexión muerta —
  backlog.
