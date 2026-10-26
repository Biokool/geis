"""Router de catálogos: SCIAN con intensidades térmicas y filtros geo."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1._common import lineage
from app.db.session import get_db
from app.schemas.catalogs import GeoFiltersOut, ScianListResponse, ScianOut

router = APIRouter(prefix="/catalogs", tags=["catalogs"])

#: Columnas geográficas por fuente: (tabla, {campo lógico: columna real}).
#: En DENUE la clase SCIAN vive en ``scian_code``; en leads, en ``scian``.
_FUENTES_GEO = (
    ("prod.leads", {
        "entidad": "entidad", "municipio": "municipio",
        "colonia": "colonia", "cp": "cp", "scian": "scian",
    }),
    ("prod.denue_establishments", {
        "entidad": "entidad", "municipio": "municipio",
        "colonia": "colonia", "cp": "cp", "scian": "scian_code",
    }),
)

#: Nivel de cascada de cada campo: qué filtros recibidos lo restringen.
_NIVEL_CASCADA = {
    "entidad": (),
    "municipio": ("entidad",),
    "colonia": ("entidad", "municipio"),
    "cp": ("entidad", "municipio", "colonia"),
    "scian": ("entidad", "municipio", "colonia"),
}


def _distintos_geo(db: Session, campo: str, filtros: dict[str, str]) -> list[str]:
    """DISTINCT del campo en leads ∪ DENUE, con la cascada aplicada."""
    valores: set[str] = set()
    for tabla, columnas in _FUENTES_GEO:
        condiciones = [f"{columnas[campo]} IS NOT NULL", f"{columnas[campo]} <> ''"]
        params: dict = {}
        for previo in _NIVEL_CASCADA[campo]:
            if previo in filtros:
                condiciones.append(f"{columnas[previo]} = :f_{previo}")
                params[f"f_{previo}"] = filtros[previo]
        filas = db.execute(
            text(
                f"SELECT DISTINCT {columnas[campo]} FROM {tabla} "
                f"WHERE {' AND '.join(condiciones)}"
            ),
            params,
        ).all()
        valores.update(str(f[0]) for f in filas if f[0])
    return sorted(valores)


@router.get("/geo-filters", response_model=GeoFiltersOut)
def filtros_geograficos(
    entidad: str | None = Query(default=None, description="Restringe la cascada a esta entidad"),
    municipio: str | None = Query(default=None, description="Restringe la cascada a este municipio"),
    colonia: str | None = Query(default=None, description="Restringe CPs y SCIAN a esta colonia"),
    db: Session = Depends(get_db),
):
    """Valores geográficos disponibles, en cascada entidad→municipio→colonia.

    Fuentes: ``prod.leads`` (geografía derivada, migración 0005) y
    ``prod.denue_establishments`` (ya trae los campos), así la cascada
    funciona aunque los leads aún no estén enriquecidos. Los municipios
    se restringen por ``entidad``; las colonias por entidad+municipio;
    CPs y SCIAN por entidad+municipio+colonia. Sin nulos ni vacíos.
    """
    filtros = {
        campo: valor
        for campo, valor in (
            ("entidad", entidad), ("municipio", municipio),
            ("colonia", colonia),
        )
        if valor
    }
    return GeoFiltersOut(
        entidades=_distintos_geo(db, "entidad", filtros),
        municipios=_distintos_geo(db, "municipio", filtros),
        colonias=_distintos_geo(db, "colonia", filtros),
        cps=_distintos_geo(db, "cp", filtros),
        scians=_distintos_geo(db, "scian", filtros),
    )


@router.get("/scian", response_model=ScianListResponse)
def listar_scian(
    q: str | None = Query(
        default=None,
        description="Filtra por código o descripción (búsqueda libre del campo SCIAN)",
    ),
    db: Session = Depends(get_db),
):
    """Catálogo SCIAN con intensidad térmica (IDT) y atractivo base (Huff).

    ``q`` es opcional: si viene, filtra por código o descripción. El
    análisis acepta cualquier SCIAN del DENUE aunque no esté en este
    catálogo semilla (se usan parámetros neutros y se advierte).
    """
    sql = (
        "SELECT scian_code, description, sector_code, thermal_intensity, "
        "base_attractiveness, lambda_default FROM prod.cat_scian"
    )
    params: dict = {}
    if q and q.strip():
        sql += " WHERE scian_code ILIKE :q OR description ILIKE :q"
        params["q"] = f"%{q.strip()}%"
    sql += " ORDER BY scian_code"
    filas = db.execute(text(sql), params).all()
    items = [
        ScianOut(
            scian_code=f[0], description=f[1], sector_code=f[2],
            thermal_intensity=float(f[3]), base_attractiveness=float(f[4]),
            lambda_default=float(f[5]),
        )
        for f in filas
    ]
    return ScianListResponse(items=items, total=len(items), lineage=lineage(db))
