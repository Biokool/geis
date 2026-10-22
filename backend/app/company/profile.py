"""Parseo del documento PERFIL-EMPRESA.md (frontmatter YAML + cuerpo markdown).

Intenta primero con ``python-frontmatter``; si no está instalado o no
extrae el bloque (p. ej. el doc tiene texto antes del primer ``---``),
usa un parser manual mínimo: toma el texto entre las dos primeras líneas
``---`` y lo parsea con ``yaml.safe_load`` (PyYAML es dependencia
transitiva vía otros paquetes).

Devuelve ``{"profile": dict, "faltantes": [str]}`` donde ``faltantes``
lista las rutas de los campos críticos sin llenar (contienen
``[Tu respuesta aquí]``, ``[PENDIENTE]`` o están vacíos).
"""
from __future__ import annotations

import yaml

#: Marcadores de "campo sin llenar" en la plantilla (prefijos, porque la
#: plantilla a veces agrega aclaraciones: "[Tu respuesta aquí — ej: ...]").
_PLACEHOLDERS = ("[tu respuesta aquí", "[pendiente]")


def _extraer_frontmatter_manual(texto: str) -> dict:
    """Extrae el bloque YAML entre las dos primeras líneas `---`."""
    lineas = texto.splitlines()
    inicio = fin = None
    for i, linea in enumerate(lineas):
        if linea.strip() == "---":
            if inicio is None:
                inicio = i
            else:
                fin = i
                break
    if inicio is None or fin is None or fin <= inicio + 1:
        return {}
    bloque = "\n".join(lineas[inicio + 1 : fin])
    try:
        datos = yaml.safe_load(bloque)
    except yaml.YAMLError:
        return {}
    return datos if isinstance(datos, dict) else {}


def _extraer_frontmatter(texto: str) -> dict:
    """Frontmatter vía librería si funciona; si no, parser manual."""
    try:
        import frontmatter  # type: ignore

        try:
            post = frontmatter.loads(texto)
            if isinstance(post.metadata, dict) and "empresa" in post.metadata:
                return post.metadata
        except Exception:
            pass
    except ImportError:
        pass
    return _extraer_frontmatter_manual(texto)


def es_faltante(valor: object) -> bool:
    """True si el valor es un marcador de campo sin llenar."""
    if valor is None:
        return True
    s = str(valor).strip()
    if not s:
        return True
    return any(m in s.lower() for m in _PLACEHOLDERS)


def _producto_valido(producto: object) -> bool:
    return (
        isinstance(producto, dict)
        and not es_faltante(producto.get("nombre"))
    )


def validar_criticos(perfil: dict) -> list[str]:
    """Valida los campos críticos y devuelve la lista de faltantes.

    Críticos: ``empresa.nombre``, ``vertical.id``, al menos 1 producto
    válido en ``productos``, ``cliente_ideal`` (descripción) y
    ``territorio`` (estados o ciudades).
    """
    faltantes: list[str] = []
    empresa = perfil.get("empresa") or {}
    vertical = perfil.get("vertical") or {}
    cliente = perfil.get("cliente_ideal") or {}
    territorio = perfil.get("territorio") or {}

    if es_faltante(empresa.get("nombre")):
        faltantes.append("empresa.nombre")
    if es_faltante(vertical.get("id")):
        faltantes.append("vertical.id")

    productos = perfil.get("productos") or []
    if not isinstance(productos, list) or not any(
        _producto_valido(p) for p in productos
    ):
        faltantes.append("productos (se requiere al menos 1 producto con nombre)")

    if es_faltante(cliente.get("descripcion")):
        faltantes.append("cliente_ideal.descripcion")
    if es_faltante(territorio.get("estados")) and es_faltante(
        territorio.get("ciudades")
    ):
        faltantes.append("territorio (estados o ciudades)")

    return faltantes


def parse_markdown(texto: str) -> dict:
    """Parsea el documento de perfil.

    :returns: ``{"profile": dict_del_frontmatter, "faltantes": [str]}``.
    """
    perfil = _extraer_frontmatter(texto)
    return {"profile": perfil, "faltantes": validar_criticos(perfil)}


def parse_archivo(ruta: str) -> dict:
    """Lee un archivo .md de perfil y lo parsea."""
    with open(ruta, encoding="utf-8") as f:
        return parse_markdown(f.read())
