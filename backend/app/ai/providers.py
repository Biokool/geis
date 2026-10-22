"""Proveedores de IA con fallback ordenado.

Interfaz común: ``chat(system, messages) -> str``. Las API keys se leen
del entorno (``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``, ``GEMINI_API_KEY``,
``GROQ_API_KEY``, ``DEEPSEEK_API_KEY``, ``OPENROUTER_API_KEY``,
``NVIDIA_API_KEY``, ``CLOUDFLARE_API_TOKEN`` + ``CLOUDFLARE_ACCOUNT_ID``);
el orden de intento sale de ``AI_DEFAULT_ORDER``
(default: ``openai,anthropic,gemini,groq,deepseek,openrouter,nvidia,cloudflare``).

OpenRouter, NVIDIA NIM y Cloudflare Workers AI se consumen vía su
endpoint compatible con OpenAI. Si ningún proveedor responde se lanza
``AIProviderError`` honesto. ``_last_ok`` registra el último resultado
por proveedor para ``/ai/status``.
"""
from __future__ import annotations

import os

import httpx

#: Proveedores soportados, en orden canónico.
PROVIDERS = (
    "openai",
    "anthropic",
    "gemini",
    "groq",
    "deepseek",
    "openrouter",
    "nvidia",
    "cloudflare",
)

#: Orden por defecto (también usado cuando AI_DEFAULT_ORDER no está definido).
DEFAULT_ORDER = ",".join(PROVIDERS)

#: Timeout de las llamadas HTTP (s).
TIMEOUT_S = 60.0

#: Último resultado por proveedor: True/False, None si nunca se intentó.
_last_ok: dict[str, bool | None] = {p: None for p in PROVIDERS}


class AIProviderError(RuntimeError):
    """Ningún proveedor de IA configurado o disponible."""


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def configured(name: str) -> bool:
    """True si el proveedor tiene credenciales configuradas.

    Cloudflare Workers AI requiere token **y** account ID; el resto solo
    su ``{NOMBRE}_API_KEY``.
    """
    if name == "cloudflare":
        return bool(_env("CLOUDFLARE_API_TOKEN") and _env("CLOUDFLARE_ACCOUNT_ID"))
    return bool(_env(f"{name.upper()}_API_KEY"))


def provider_order() -> list[str]:
    """Orden de fallback desde AI_DEFAULT_ORDER (solo nombres válidos)."""
    raw = _env("AI_DEFAULT_ORDER") or DEFAULT_ORDER
    orden = [p.strip().lower() for p in raw.split(",")]
    vistos: list[str] = []
    for p in orden:
        if p in PROVIDERS and p not in vistos:
            vistos.append(p)
    for p in PROVIDERS:
        if p not in vistos:
            vistos.append(p)
    return vistos


def last_status() -> list[dict]:
    """Estado para GET /ai/status."""
    return [
        {"name": p, "configured": configured(p), "last_ok": _last_ok[p]}
        for p in PROVIDERS
    ]


def _post(url: str, *, headers: dict | None = None, payload: dict) -> httpx.Response:
    """POST HTTP (punto único, fácil de mockear en tests)."""
    with httpx.Client(timeout=TIMEOUT_S) as client:
        resp = client.post(url, headers=headers or {}, json=payload)
    resp.raise_for_status()
    return resp


def _openai(system: str, messages: list[dict]) -> str:
    resp = _post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {_env('OPENAI_API_KEY')}"},
        payload={
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": system}, *messages],
        },
    )
    return resp.json()["choices"][0]["message"]["content"]


def _anthropic(system: str, messages: list[dict]) -> str:
    resp = _post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": _env("ANTHROPIC_API_KEY"),
            "anthropic-version": "2023-06-01",
        },
        payload={
            "model": "claude-3-5-haiku-latest",
            "max_tokens": 2000,
            "system": system,
            "messages": messages,
        },
    )
    bloques = resp.json().get("content", [])
    return "".join(b.get("text", "") for b in bloques if b.get("type") == "text")


def _gemini(system: str, messages: list[dict]) -> str:
    # Gemini: el system prompt se antepone como primer turno de usuario.
    contenidos = [{"role": "user", "parts": [{"text": system}]}]
    for m in messages:
        rol = "model" if m.get("role") == "assistant" else "user"
        contenidos.append({"role": rol, "parts": [{"text": m.get("content", "")}]})
    resp = _post(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={_env('GEMINI_API_KEY')}",
        payload={"contents": contenidos},
    )
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _groq(system: str, messages: list[dict]) -> str:
    resp = _post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {_env('GROQ_API_KEY')}"},
        payload={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "system", "content": system}, *messages],
        },
    )
    return resp.json()["choices"][0]["message"]["content"]


def _deepseek(system: str, messages: list[dict]) -> str:
    resp = _post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {_env('DEEPSEEK_API_KEY')}"},
        payload={
            "model": "deepseek-chat",
            "messages": [{"role": "system", "content": system}, *messages],
        },
    )
    return resp.json()["choices"][0]["message"]["content"]


def _openai_compatible(
    system: str,
    messages: list[dict],
    *,
    url: str,
    key: str,
    model: str,
    extra_headers: dict | None = None,
) -> str:
    """Llamada estilo OpenAI ``/chat/completions`` (OpenRouter, NVIDIA, Cloudflare)."""
    headers = {"Authorization": f"Bearer {key}", **(extra_headers or {})}
    resp = _post(
        url,
        headers=headers,
        payload={
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
        },
    )
    return resp.json()["choices"][0]["message"]["content"]


def _openrouter(system: str, messages: list[dict]) -> str:
    return _openai_compatible(
        system,
        messages,
        url="https://openrouter.ai/api/v1/chat/completions",
        key=_env("OPENROUTER_API_KEY"),
        model=_env("OPENROUTER_MODEL") or "openai/gpt-4o-mini",
        extra_headers={
            "HTTP-Referer": "https://geis.local",
            "X-Title": "GEIS",
        },
    )


def _nvidia(system: str, messages: list[dict]) -> str:
    return _openai_compatible(
        system,
        messages,
        url="https://integrate.api.nvidia.com/v1/chat/completions",
        key=_env("NVIDIA_API_KEY"),
        model=_env("NVIDIA_MODEL") or "meta/llama-3.3-70b-instruct",
    )


def _cloudflare(system: str, messages: list[dict]) -> str:
    account = _env("CLOUDFLARE_ACCOUNT_ID")
    return _openai_compatible(
        system,
        messages,
        url=(
            f"https://api.cloudflare.com/client/v4/accounts/{account}"
            f"/ai/v1/chat/completions"
        ),
        key=_env("CLOUDFLARE_API_TOKEN"),
        model=_env("CLOUDFLARE_MODEL")
        or "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    )


_LLAMADAS = {
    "openai": _openai,
    "anthropic": _anthropic,
    "gemini": _gemini,
    "groq": _groq,
    "deepseek": _deepseek,
    "openrouter": _openrouter,
    "nvidia": _nvidia,
    "cloudflare": _cloudflare,
}


def chat_with_provider(
    system: str, messages: list[dict], purpose: str = ""
) -> tuple[str, str]:
    """Intenta los proveedores en orden; devuelve (proveedor, texto).

    Registra el resultado en ``_last_ok``. Si ninguno responde lanza
    ``AIProviderError``.
    """
    errores: list[str] = []
    for nombre in provider_order():
        if not configured(nombre):
            continue
        try:
            texto = _LLAMADAS[nombre](system, messages)
            _last_ok[nombre] = True
            return nombre, texto
        except Exception as exc:  # noqa: BLE001 — se acumula el motivo
            _last_ok[nombre] = False
            errores.append(f"{nombre}: {exc}")
    detalle = "; ".join(errores) if errores else "sin API keys configuradas"
    raise AIProviderError(
        f"ningún proveedor de IA configurado o disponible ({detalle})"
    )


def chat(system: str, messages: list[dict], purpose: str = "") -> str:
    """Interfaz común: devuelve solo el texto de la respuesta."""
    _, texto = chat_with_provider(system, messages, purpose=purpose)
    return texto
