"""Router de la IA interna: estado, chat con el operador y llenado de perfil."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai import operator, providers
from app.company import store
from app.company.schemas import ChatBody, FillProfileBody
from app.db.session import get_db

router = APIRouter(prefix="/ai", tags=["ai"])

#: Prompt estricto para llenar la plantilla PERFIL-EMPRESA.md.
_SYSTEM_FILL = (
    "Eres un asistente que llena la plantilla PERFIL-EMPRESA.md. "
    "No inventes cifras ni datos; lo que no encuentres márcalo como "
    "[PENDIENTE]. Devuelve SOLO el markdown completo con el frontmatter "
    "YAML válido."
)

#: Máximo de caracteres de contexto web para fill-profile.
_MAX_CTX_CHARS = 30_000


@router.get("/status")
def estado_ia():
    """Estado de los proveedores: configurado y último resultado."""
    return {"providers": providers.last_status()}


@router.post("/chat")
def chatear(body: ChatBody, db: Session = Depends(get_db)):
    """Conversación con el operador híbrido."""
    vertical_id = store.active_vertical_id(db)
    historial = [{"role": m.role, "content": m.content} for m in body.history]
    return operator.chat(body.message, historial, vertical_id, db)


def _descargar_texto(url: str) -> str:
    """Descarga texto plano de una URL (timeout 20s, máx 30k caracteres)."""
    import httpx

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "GEIS-ai/1.0"})
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if "text" not in ctype and "json" not in ctype and "xml" not in ctype:
            raise HTTPException(
                status_code=422,
                detail=f"la URL no devolvió texto (content-type: {ctype})",
            )
        texto = resp.text
    # Recorte honesto: solo los primeros 30k caracteres.
    if len(texto) > _MAX_CTX_CHARS:
        texto = texto[:_MAX_CTX_CHARS] + "\n[...recortado a 30k caracteres...]"
    return texto


@router.post("/fill-profile")
def llenar_perfil(body: FillProfileBody):
    """Llena la plantilla PERFIL-EMPRESA.md con IA a partir de una URL o
    texto. Devuelve {markdown, pendientes}."""
    if not body.url and not body.text:
        raise HTTPException(
            status_code=422, detail="se requiere 'url' o 'text'"
        )
    partes: list[str] = []
    if body.url:
        try:
            partes.append(f"Contenido de {body.url}:\n{_descargar_texto(body.url)}")
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — se reporta
            raise HTTPException(
                status_code=422, detail=f"no se pudo descargar la URL: {exc}"
            )
    if body.text:
        partes.append(f"Texto proporcionado{f' ({body.filename})' if body.filename else ''}:\n{body.text}")
    contexto = "\n\n".join(partes)
    if len(contexto) > _MAX_CTX_CHARS:
        contexto = contexto[:_MAX_CTX_CHARS]

    try:
        markdown = providers.chat(
            _SYSTEM_FILL,
            [{"role": "user", "content": contexto}],
            purpose="fill_profile",
        )
    except providers.AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    pendientes = sorted({
        linea.strip()[:200]
        for linea in markdown.splitlines()
        if "[PENDIENTE]" in linea
    })
    return {"markdown": markdown, "pendientes": pendientes}
