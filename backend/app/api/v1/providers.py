"""Router de providers: capa anti-cautiverio (local/cloud/disabled)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.radar import Provider
from app.schemas.radar import ProviderOut, ProviderUpdate

router = APIRouter(prefix="/providers", tags=["providers"])


def _to_out(p: Provider) -> ProviderOut:
    return ProviderOut(
        name=p.name,
        kind=p.kind,
        mode=p.mode,
        provider=p.provider,
        config=p.config or {},
        enabled=p.enabled,
    )


@router.get("", response_model=list[ProviderOut])
def listar_providers(db: Session = Depends(get_db)):
    """Lista todos los providers con su modo actual."""
    return [_to_out(p) for p in db.query(Provider).order_by(Provider.name).all()]


@router.get("/{name}", response_model=ProviderOut)
def obtener_provider(name: str, db: Session = Depends(get_db)):
    """Detalle de un provider por nombre."""
    p = db.get(Provider, name)
    if p is None:
        raise HTTPException(status_code=404, detail=f"provider {name!r} no encontrado")
    return _to_out(p)


def _error_coherencia(mode: str, provider: str) -> str | None:
    """Coherencia modo/backend (regla R11 del inventario Radar).

    ``mode='cloud'`` exige un backend de nube (≠ 'local') y
    ``mode='local'`` exige ``provider='local'``. Devuelve el motivo o
    None si el par es coherente.
    """
    if mode == "cloud" and provider == "local":
        return "mode='cloud' exige un backend de nube (provider != 'local')"
    if mode == "local" and provider != "local":
        return "mode='local' exige provider='local'"
    return None


@router.put("/{name}", response_model=ProviderOut)
def actualizar_provider(name: str, payload: ProviderUpdate, db: Session = Depends(get_db)):
    """Crea o actualiza un provider (mode, provider, config, enabled).

    Si la petición define el par (mode, provider), se valida su
    coherencia (regla R11) y un par incoherente se rechaza con 422.
    Los cambios de un solo campo (p. ej. el toggle de modo del frontend,
    que envía solo ``{mode}``) no se bloquean: la coherencia se juzga
    sobre el par explícito, no sobre el estado parcial resultante.
    """
    if payload.mode is not None and payload.provider is not None:
        error = _error_coherencia(payload.mode, payload.provider)
        if error:
            raise HTTPException(status_code=422, detail=error)
    p = db.get(Provider, name)
    if p is None:
        p = Provider(name=name, kind=payload.provider or "custom")
        db.add(p)
    if payload.mode is not None:
        p.mode = payload.mode
    if payload.provider is not None:
        p.provider = payload.provider
    if payload.config is not None:
        p.config = payload.config
    if payload.enabled is not None:
        p.enabled = payload.enabled
    db.commit()
    db.refresh(p)
    return _to_out(p)
