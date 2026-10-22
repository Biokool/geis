"""Router del perfil de empresa (configuración inicial del ecosistema)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.company import derive as derive_mod
from app.company import profile as profile_mod
from app.company import store
from app.company.schemas import DeriveBody, ProfileOut, ProfilePutBody
from app.db.session import get_db
from app.models.company import CompanyProfile

router = APIRouter(prefix="/company", tags=["company"])


def _a_out(fila: CompanyProfile, faltantes: list[str] | None = None) -> ProfileOut:
    return ProfileOut(
        id=fila.id,
        vertical_id=fila.vertical_id,
        nombre=fila.nombre,
        version=fila.version,
        is_active=fila.is_active,
        faltantes=faltantes if faltantes is not None else [],
        created_at=fila.created_at,
    )


@router.get("/profile", response_model=ProfileOut)
def obtener_perfil(db: Session = Depends(get_db)):
    """Devuelve el perfil de empresa activo (404 honesto si no hay)."""
    fila = store.get_active_profile(db)
    if fila is None:
        raise HTTPException(
            status_code=404, detail="no hay perfil de empresa activo"
        )
    parsed = profile_mod.parse_markdown(fila.profile_md or "")
    return _a_out(fila, parsed["faltantes"])


@router.put("/profile", response_model=ProfileOut)
def guardar_perfil(body: ProfilePutBody, db: Session = Depends(get_db)):
    """Parsea y valida el markdown, guarda una nueva versión (desactiva
    la anterior) y devuelve {id, version, faltantes}."""
    parsed = profile_mod.parse_markdown(body.markdown)
    perfil = parsed["profile"]
    empresa = perfil.get("empresa") or {}
    vertical = perfil.get("vertical") or {}

    anterior = store.get_active_profile(db)
    nueva_version = (anterior.version + 1) if anterior else 1
    if anterior:
        anterior.is_active = False

    fila = CompanyProfile(
        vertical_id=str(vertical.get("id", "") or "").strip() or None,
        nombre=str(empresa.get("nombre", "") or "").strip() or None,
        profile_md=body.markdown,
        profile_json=perfil,
        version=nueva_version,
        is_active=True,
    )
    db.add(fila)
    db.commit()
    db.refresh(fila)
    store.invalidate_cache()
    return _a_out(fila, parsed["faltantes"])


@router.post("/profile/derive")
def previsualizar_config(body: DeriveBody, db: Session = Depends(get_db)):
    """Deriva la VerticalConfig sin guardar (preview).

    Si no viene ``markdown``, usa el perfil activo.
    """
    if body.markdown:
        parsed = profile_mod.parse_markdown(body.markdown)
        perfil = parsed["profile"]
        faltantes = parsed["faltantes"]
    else:
        fila = store.get_active_profile(db)
        if fila is None:
            raise HTTPException(
                status_code=404, detail="no hay perfil activo ni markdown"
            )
        perfil = dict(fila.profile_json or {})
        faltantes = profile_mod.validar_criticos(perfil)
    cfg = derive_mod.derive_config(perfil)
    data = cfg.model_dump()
    data["faltantes"] = faltantes
    return data


@router.post("/profile/activate/{profile_id}", response_model=ProfileOut)
def activar_perfil(profile_id: int, db: Session = Depends(get_db)):
    """Activa una versión del historial (desactiva la actual)."""
    fila = db.get(CompanyProfile, profile_id)
    if fila is None:
        raise HTTPException(
            status_code=404, detail=f"perfil {profile_id} no encontrado"
        )
    db.query(CompanyProfile).filter(
        CompanyProfile.is_active.is_(True)
    ).update({"is_active": False})
    fila.is_active = True
    db.commit()
    db.refresh(fila)
    store.invalidate_cache()
    parsed = profile_mod.parse_markdown(fila.profile_md or "")
    return _a_out(fila, parsed["faltantes"])


@router.get("/profiles", response_model=list[ProfileOut])
def historial_perfiles(db: Session = Depends(get_db)):
    """Historial de versiones del perfil (más recientes primero)."""
    filas = (
        db.query(CompanyProfile)
        .order_by(CompanyProfile.version.desc())
        .all()
    )
    return [_a_out(f) for f in filas]
