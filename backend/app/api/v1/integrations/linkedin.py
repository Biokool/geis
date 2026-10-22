"""Integración LinkedIn: OAuth real parametrizado por variables de entorno.

El flujo requiere una app de LinkedIn con permisos
``r_organization_social`` + ``w_organization_social`` (Community
Management API). Los tokens viven en el entorno (LINKEDIN_ACCESS_TOKEN)
o en el vault; nunca se queman credenciales en código.

Sin credenciales configuradas los endpoints devuelven 501 con el motivo
documentado (no verificable en este entorno, riesgo R-02 del blueprint).
"""
from __future__ import annotations

import os
import secrets
import urllib.parse

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/integrations/linkedin", tags=["integrations"])

#: Scopes requeridos por el workflow radar-05 (stats de la página).
SCOPES = ["r_organization_social", "w_organization_social"]

_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"


def _client_id() -> str:
    return os.getenv("LINKEDIN_CLIENT_ID", "")


def _client_secret() -> str:
    return os.getenv("LINKEDIN_CLIENT_SECRET", "")


def _redirect_uri() -> str:
    return os.getenv("LINKEDIN_REDIRECT_URI", "")


@router.get("/auth")
def iniciar_auth() -> dict:
    """Devuelve la URL de autorización de LinkedIn para redirigir al usuario.

    501 si falta LINKEDIN_CLIENT_ID o LINKEDIN_REDIRECT_URI.
    """
    client_id = _client_id()
    redirect_uri = _redirect_uri()
    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=501,
            detail={
                "error": "linkedin_no_configurado",
                "motivo": (
                    "Faltan LINKEDIN_CLIENT_ID y/o LINKEDIN_REDIRECT_URI en el "
                    "entorno. Crea una app en https://developer.linkedin.com, "
                    "solicita los permisos r_organization_social y "
                    "w_organization_social (Community Management API) y "
                    "configura las variables; el flujo OAuth no es verificable "
                    "sin una app real (riesgo R-02 del blueprint)."
                ),
            },
        )
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "state": secrets.token_urlsafe(16),
    }
    return {
        "auth_url": f"{_AUTH_URL}?{urllib.parse.urlencode(params)}",
        "scopes": SCOPES,
    }


@router.get("/callback")
def callback(code: str | None = Query(default=None)) -> dict:
    """Recibe el ``code`` de LinkedIn e intenta intercambiarlo por un token.

    Sin credenciales configuradas, o si el intercambio falla, devuelve 501
    documentado (el token debe guardarse luego en LINKEDIN_ACCESS_TOKEN).
    """
    if not code:
        raise HTTPException(status_code=400, detail="falta el parámetro 'code'")
    client_id, client_secret, redirect_uri = (
        _client_id(),
        _client_secret(),
        _redirect_uri(),
    )
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(
            status_code=501,
            detail={
                "error": "linkedin_no_configurado",
                "motivo": (
                    "Faltan LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET y/o "
                    "LINKEDIN_REDIRECT_URI; no se puede completar el "
                    "intercambio del code sin credenciales de app real."
                ),
            },
        )
    try:
        resp = httpx.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        datos = resp.json()
    except Exception as exc:  # noqa: BLE001 — se reporta el motivo
        raise HTTPException(
            status_code=501,
            detail={
                "error": "intercambio_fallido",
                "motivo": (
                    "El intercambio del code con LinkedIn falló; verifica la "
                    "app, los permisos y que el code no haya expirado. "
                    f"Detalle: {exc}"
                ),
            },
        ) from exc
    # El token se guarda fuera del proceso (vault/.env); aquí solo se
    # confirma el intercambio sin exponerlo.
    return {
        "ok": True,
        "token_type": datos.get("token_type"),
        "expires_in": datos.get("expires_in"),
        "nota": (
            "Intercambio exitoso. Guarda el access_token como "
            "LINKEDIN_ACCESS_TOKEN en el entorno (no se devuelve por la API)."
        ),
    }


@router.get("/status")
def estado() -> dict:
    """Indica si hay un token de LinkedIn disponible en el entorno."""
    conectado = bool(os.getenv("LINKEDIN_ACCESS_TOKEN", ""))
    return {
        "connected": conectado,
        "scopes_requeridos": SCOPES,
        "nota": (
            "Conectado vía LINKEDIN_ACCESS_TOKEN del entorno."
            if conectado
            else "Sin token. Completa /auth y /callback, o configura "
            "LINKEDIN_ACCESS_TOKEN manualmente."
        ),
    }


@router.post("/disconnect")
def desconectar() -> dict:
    """Limpia el token del proceso actual.

    Nota: el token persistente vive en el .env/vault; elimínalo ahí para
    una desconexión definitiva.
    """
    os.environ.pop("LINKEDIN_ACCESS_TOKEN", None)
    return {
        "connected": False,
        "nota": (
            "Token removido del proceso. Si LINKEDIN_ACCESS_TOKEN está en el "
            ".env o el vault, elimínalo ahí para desconectar de forma "
            "permanente."
        ),
    }
