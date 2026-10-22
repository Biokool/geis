"""Operador híbrido: herramientas locales primero, IA como respaldo.

Cada herramienta es un dict ``{name, description, parameters, executor}``
donde ``executor(args, ctx)`` recibe ``ctx = {"db", "vertical_id"}``.

Lógica híbrida: el executor consulta primero lo local (DB / knowledge);
si no hay dato, llama al primer proveedor de IA disponible, guarda el
resultado en ``knowledge_facts`` con ``source='ai:{provider}'`` y
``confidence`` 0.7 (default para IA), y devuelve el dato. Cada uso de IA
se registra en ``ai_usage_log`` (provider, purpose, ok).

``chat(message, history, vertical_id, db)`` orquesta: pide a la IA que
responda o invoque herramientas con el formato ``TOOL: nombre {json}``
(una por línea); parsea, ejecuta, reinyecta el resultado y pide la
respuesta final (máx 3 rondas).
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.ai import knowledge, providers
from app.models.company import AiUsageLog

#: Confianza por defecto de los hechos generados por IA.
CONF_AI = 0.7

#: Máximo de rondas herramienta → respuesta en ``chat``.
MAX_RONDAS = 3

_TOOL_RE = re.compile(r"^TOOL:\s*([a-z_][a-z0-9_]*)\s*(\{.*\})?\s*$", re.M)


def _uso(db: Session, provider: str, purpose: str, ok: bool) -> None:
    """Registra un uso de IA en ai_usage_log (nunca rompe el flujo)."""
    try:
        db.add(AiUsageLog(provider=provider, purpose=purpose, ok=ok))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _ia_y_guarda(
    db: Session, vertical_id: str, fact_key: str, system: str,
    prompt: str, purpose: str, confidence: float = CONF_AI,
) -> dict:
    """Llama a la IA, guarda el resultado como hecho y lo devuelve."""
    try:
        provider, texto = providers.chat_with_provider(
            system, [{"role": "user", "content": prompt}], purpose=purpose
        )
        _uso(db, provider, purpose, True)
    except providers.AIProviderError:
        _uso(db, "", purpose, False)
        raise
    hecho = knowledge.save_fact(
        db, vertical_id, fact_key,
        {"texto": texto, "pregunta": prompt},
        source=f"ai:{provider}", confidence=confidence,
    )
    hecho["texto"] = texto
    return hecho


# ------------------------------------------------------------------ tools
def _t_company_summary(args: dict, ctx: dict) -> dict:
    from app.company.store import get_active_config

    cfg = get_active_config(ctx["db"])
    if not cfg:
        return {
            "estado": "sin_perfil",
            "nota": "No hay perfil de empresa activo; la IA no puede "
                    "inventar los datos de la empresa. Carga el perfil con "
                    "PUT /company/profile.",
        }
    return {
        "estado": "ok",
        "origen": "local",
        "empresa": cfg.get("nombre_empresa"),
        "vertical_id": cfg.get("vertical_id"),
        "productos": [t["producto"] for t in cfg.get("tam_defaults", [])],
        "scian_targets": cfg.get("scian_targets", []),
        "canales": cfg.get("outreach_channels", []),
        "territorio_nota": "ver perfil completo en GET /company/profile",
    }


def _t_territory_analysis(args: dict, ctx: dict) -> dict:
    from app.api.v1.analysis import compute_location_analysis

    db, vertical_id = ctx["db"], ctx["vertical_id"]
    lat, lon = args.get("lat"), args.get("lon")
    if lat is not None and lon is not None:
        try:
            res = compute_location_analysis(
                db, args.get("giro"), args.get("scian"),
                float(lat), float(lon), args.get("radios") or [1000, 2000],
            )
            return {"estado": "ok", "origen": "local", "analisis": res}
        except Exception as exc:  # noqa: BLE001 — se reporta
            return {"estado": "error", "origen": "local", "detalle": str(exc)}
    # Sin coordenadas no hay cálculo posible: guía general vía IA.
    giro = args.get("giro") or "giro no especificado"
    hecho = _ia_y_guarda(
        db, vertical_id, f"territory_guide:{giro}",
        "Eres un analista de geomarketing. Das marcos de análisis generales, "
        "nunca cifras inventadas.",
        f"Da un marco general (sin cifras inventadas) para evaluar "
        f"territorios para el giro «{giro}»: qué mirar en demanda, "
        f"competencia y accesibilidad.",
        purpose="tool:territory_analysis",
    )
    return {"estado": "ok", "origen": "ia", "guia": hecho.get("texto")}


def _t_score_lead(args: dict, ctx: dict) -> dict:
    from app.analytics.scoring_unificado import score_unificado

    componentes = args.get("componentes") or {}
    if not componentes:
        return {
            "estado": "error",
            "nota": "score_lead necesita 'componentes' "
                    "(idt, tamano, acceso, densidad, contacto, ...). "
                    "La IA no estima scores sin datos.",
        }
    vertical = args.get("vertical") or ctx["vertical_id"]
    try:
        res = score_unificado(componentes, vertical=vertical)
        return {"estado": "ok", "origen": "local", "score": res}
    except Exception as exc:  # noqa: BLE001
        return {"estado": "error", "detalle": str(exc)}


def _t_report_section(args: dict, ctx: dict) -> dict:
    db, vertical_id = ctx["db"], ctx["vertical_id"]
    seccion = args.get("seccion") or "general"
    local = knowledge.get_fact(db, vertical_id, f"report_section:{seccion}")
    if local:
        return {"estado": "ok", "origen": "local", "seccion": local}
    contexto = args.get("contexto") or ""
    hecho = _ia_y_guarda(
        db, vertical_id, f"report_section:{seccion}",
        "Eres un redactor de reportes de geomarketing. Escribes secciones "
        "claras y honestas; si un dato falta, lo declaras en vez de inventarlo.",
        f"Redacta la sección «{seccion}» de un reporte de ubicación. "
        f"Contexto: {contexto}",
        purpose="tool:report_section",
    )
    return {"estado": "ok", "origen": "ia", "seccion": hecho.get("texto")}


def _t_get_knowledge(args: dict, ctx: dict) -> dict:
    db, vertical_id = ctx["db"], ctx["vertical_id"]
    key = args.get("key") or ""
    local = knowledge.get_fact(db, vertical_id, key)
    if local:
        return {"estado": "ok", "origen": "local", "hecho": local}
    pregunta = args.get("pregunta") or f"Información sobre «{key}»"
    hecho = _ia_y_guarda(
        db, vertical_id, key,
        "Eres un asistente de geomarketing. Respondes con información útil "
        "y honesta; si no sabes algo, lo dices.",
        pregunta,
        purpose="tool:get_knowledge",
    )
    return {"estado": "ok", "origen": "ia", "hecho": hecho}


def _t_save_fact(args: dict, ctx: dict) -> dict:
    db, vertical_id = ctx["db"], ctx["vertical_id"]
    hecho = knowledge.save_fact(
        db, vertical_id, args.get("key", ""),
        args.get("value") or {},
        source=args.get("source", "manual"),
        confidence=float(args.get("confidence", 1.0)),
    )
    return {"estado": "ok", "origen": "local", "hecho": hecho}


def _t_suggest_scian(args: dict, ctx: dict) -> dict:
    from app.company.store import get_active_config

    db, vertical_id = ctx["db"], ctx["vertical_id"]
    cfg = get_active_config(db)
    if cfg and cfg.get("scian_targets"):
        return {
            "estado": "ok", "origen": "local",
            "scian": cfg["scian_targets"],
            "nota": "SCIAN sugeridos del perfil de empresa.",
        }
    giro = args.get("giro") or args.get("descripcion") or "giro no especificado"
    hecho = _ia_y_guarda(
        db, vertical_id, f"scian_sugerido:{giro}",
        "Eres un especialista en el clasificador SCIAN de México. "
        "Sugieres códigos SCIAN probables y adviertes que deben validarse "
        "en el DENUE; nunca inventas certeza.",
        f"Sugiere códigos SCIAN probables para el giro «{giro}» en México, "
        f"con una línea de por qué cada uno.",
        purpose="tool:suggest_scian",
    )
    return {"estado": "ok", "origen": "ia", "sugerencia": hecho.get("texto")}


Executor = Callable[[dict, dict], dict]

TOOLS: list[dict] = [
    {
        "name": "company_summary",
        "description": "Resumen de la empresa activa (nombre, vertical, "
                       "productos, SCIAN, canales). Sin argumentos.",
        "parameters": {"type": "object", "properties": {}},
        "executor": _t_company_summary,
    },
    {
        "name": "territory_analysis",
        "description": "Análisis de ubicación. Con lat/lon calcula el "
                       "análisis interno (ISM/TAM/Huff); sin coordenadas da "
                       "una guía general vía IA.",
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {"type": "number"}, "lon": {"type": "number"},
                "giro": {"type": "string"}, "scian": {"type": "string"},
                "radios": {"type": "array", "items": {"type": "number"}},
            },
        },
        "executor": _t_territory_analysis,
    },
    {
        "name": "score_lead",
        "description": "Calcula el score unificado 0–100 de un lead. "
                       "Requiere 'componentes' (dict) y opcionalmente "
                       "'vertical'.",
        "parameters": {
            "type": "object",
            "properties": {
                "componentes": {"type": "object"},
                "vertical": {"type": "string"},
            },
            "required": ["componentes"],
        },
        "executor": _t_score_lead,
    },
    {
        "name": "report_section",
        "description": "Obtiene o redacta la sección de un reporte "
                       "(parámetros: seccion, contexto).",
        "parameters": {
            "type": "object",
            "properties": {
                "seccion": {"type": "string"},
                "contexto": {"type": "string"},
            },
            "required": ["seccion"],
        },
        "executor": _t_report_section,
    },
    {
        "name": "get_knowledge",
        "description": "Lee un hecho del conocimiento del vertical "
                       "(parámetros: key, pregunta opcional). Si no existe, "
                       "lo genera con IA y lo guarda.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "pregunta": {"type": "string"},
            },
            "required": ["key"],
        },
        "executor": _t_get_knowledge,
    },
    {
        "name": "save_fact",
        "description": "Guarda un hecho en el conocimiento (key, value, "
                       "source opcional, confidence opcional).",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "object"},
                "source": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["key", "value"],
        },
        "executor": _t_save_fact,
    },
    {
        "name": "suggest_scian",
        "description": "Sugiere códigos SCIAN para un giro (parámetro: "
                       "giro). Usa el perfil si los trae; si no, IA.",
        "parameters": {
            "type": "object",
            "properties": {"giro": {"type": "string"}},
        },
        "executor": _t_suggest_scian,
    },
]

_POR_NOMBRE = {t["name"]: t for t in TOOLS}


def run_tool(name: str, args: dict, db: Session, vertical_id: str) -> dict:
    """Ejecuta una herramienta por nombre."""
    herramienta = _POR_NOMBRE.get(name)
    if herramienta is None:
        return {"estado": "error", "detalle": f"herramienta desconocida: {name}"}
    try:
        return herramienta["executor"](args or {}, {"db": db, "vertical_id": vertical_id})
    except providers.AIProviderError as exc:
        return {"estado": "error", "detalle": str(exc)}
    except Exception as exc:  # noqa: BLE001 — el operador nunca truena
        return {"estado": "error", "detalle": str(exc)}


def _descripcion_herramientas() -> str:
    lineas = []
    for t in TOOLS:
        params = json.dumps(t["parameters"], ensure_ascii=False)
        lineas.append(f"- {t['name']}: {t['description']} Parámetros: {params}")
    return "\n".join(lineas)


SYSTEM_BASE = (
    "Eres el operador de IA interna del ecosistema GEIS (geomarketing). "
    "Respondes en español, con honestidad: si un dato no existe, lo declaras "
    "en vez de inventarlo.\n\n"
    "Tienes estas herramientas. Para usar una, escribe en tu respuesta una "
    "línea EXACTA con el formato:\n"
    "TOOL: nombre_de_herramienta {\"arg\": \"valor\"}\n"
    "(una herramienta por línea; el JSON va en la misma línea). "
    "Si no necesitas herramientas, responde directamente al usuario.\n\n"
    "Herramientas disponibles:\n"
)


def _parsear_tools(texto: str) -> list[tuple[str, dict]]:
    llamadas: list[tuple[str, dict]] = []
    for m in _TOOL_RE.finditer(texto or ""):
        nombre = m.group(1)
        crudo = (m.group(2) or "{}").strip()
        try:
            args = json.loads(crudo)
            if not isinstance(args, dict):
                args = {}
        except json.JSONDecodeError:
            args = {}
        llamadas.append((nombre, args))
    return llamadas


def chat(
    message: str,
    history: list[dict],
    vertical_id: str,
    db: Session,
) -> dict:
    """Conversación con el operador: devuelve {"reply", "tools_used"}."""
    system = SYSTEM_BASE + _descripcion_herramientas()
    mensajes = list(history or []) + [{"role": "user", "content": message}]
    tools_used: list[str] = []
    ultimo_texto = ""

    for _ in range(MAX_RONDAS):
        try:
            provider, texto = providers.chat_with_provider(
                system, mensajes, purpose="operator_chat"
            )
            _uso(db, provider, "operator_chat", True)
        except providers.AIProviderError as exc:
            _uso(db, "", "operator_chat", False)
            return {
                "reply": f"No puedo responder ahora: {exc}",
                "tools_used": tools_used,
            }
        ultimo_texto = texto
        llamadas = _parsear_tools(texto)
        if not llamadas:
            return {"reply": texto, "tools_used": tools_used}
        mensajes.append({"role": "assistant", "content": texto})
        for nombre, args in llamadas:
            resultado = run_tool(nombre, args, db, vertical_id)
            tools_used.append(nombre)
            mensajes.append({
                "role": "user",
                "content": f"[resultado de la herramienta {nombre}]\n"
                           f"{json.dumps(resultado, ensure_ascii=False, default=str)}\n"
                           f"Con este resultado, responde al usuario de forma final "
                           f"y clara, sin más llamadas a herramientas salvo que "
                           f"sea imprescindible.",
            })

    return {"reply": ultimo_texto, "tools_used": tools_used}
