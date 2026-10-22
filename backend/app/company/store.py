"""Acceso al perfil de empresa activo y su VerticalConfig derivada.

La configuración se cachea en memoria por ``vertical_id`` y se invalida
con :func:`invalidate_cache` cada vez que el perfil cambia (PUT/activate).

Todas las funciones fallan en silencio (devuelven None) si no hay base de
datos o no hay perfil: los flujos existentes deben seguir funcionando
igual que antes cuando no hay configuración inicial.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.company.derive import derive_config
from app.models.company import CompanyProfile

#: vertical_id -> dict de la VerticalConfig derivada.
_CACHE: dict[str, dict] = {}


def invalidate_cache() -> None:
    """Limpia la caché de configuraciones derivadas."""
    _CACHE.clear()


def get_active_profile(db: Session) -> CompanyProfile | None:
    """Devuelve la fila del perfil activo, o None si no hay."""
    try:
        return (
            db.query(CompanyProfile)
            .filter(CompanyProfile.is_active.is_(True))
            .order_by(CompanyProfile.version.desc())
            .first()
        )
    except Exception:
        return None


def _derive_dict(fila: CompanyProfile) -> dict | None:
    try:
        perfil = dict(fila.profile_json or {})
        cfg = derive_config(perfil)
        data = cfg.model_dump()
        data["profile_id"] = fila.id
        data["profile_version"] = fila.version
        return data
    except Exception:
        return None


def get_active_config(
    db: Session | None = None, vertical_id: str | None = None
) -> dict | None:
    """VerticalConfig derivada del perfil activo (dict), o None.

    Si ``db`` es None se abre una sesión propia (solo lectura). Acepta
    ``vertical_id`` para filtrar: si el perfil activo no coincide,
    devuelve None.
    """
    propia = False
    try:
        if db is None:
            from app.db.session import SessionLocal

            db = SessionLocal()
            propia = True
        fila = get_active_profile(db)
        if fila is None:
            return None
        if vertical_id is not None:
            vid = (fila.vertical_id or "").strip().lower()
            if vid != vertical_id.strip().lower():
                return None
        clave = (fila.vertical_id or "").strip().lower() or "__sin_vertical__"
        if clave not in _CACHE:
            cfg = _derive_dict(fila)
            if cfg is None:
                return None
            _CACHE[clave] = cfg
        return _CACHE[clave]
    except Exception:
        return None
    finally:
        if propia and db is not None:
            try:
                db.close()
            except Exception:
                pass


def active_vertical_id(db: Session | None = None) -> str:
    """vertical_id del perfil activo, o 'default' si no hay."""
    cfg = get_active_config(db)
    vid = (cfg or {}).get("vertical_id") or ""
    return vid.strip() or "default"


def resolve_pesos(vertical: str) -> dict[str, float] | None:
    """Pesos de scoring del perfil si su vertical coincide con la pedida.

    Coincidencia: igualdad exacta (insensible a mayúsculas) o el alias
    climatización ↔ 'biokool' (el perfil Biokool declara
    ``vertical.id: climatizacion`` y el scoring lo pide como 'biokool').
    Devuelve None cuando no hay perfil, no coincide, o algo falla: el
    llamador conserva entonces su comportamiento actual.
    """
    try:
        cfg = get_active_config()
        if not cfg:
            return None
        vid = str(cfg.get("vertical_id", "") or "").lower().strip()
        pedido = (vertical or "").lower().strip()
        coincide = vid == pedido or (
            pedido == "biokool"
            and ("clima" in vid or "koolkat" in vid)
        )
        if not coincide:
            return None
        pesos = cfg.get("scoring_weights") or {}
        return dict(pesos) if pesos else None
    except Exception:
        return None
