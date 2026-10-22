"""Esquemas del router de análisis (CU-1, CU-2, CU-3)."""
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import Lineage


class LocationAnalysisRequest(BaseModel):
    giro: str | None = Field(default=None, description="Giro en texto libre (p. ej. 'cafetería')")
    scian: str | None = Field(default=None, description="Clase SCIAN a 6 dígitos (p. ej. '722515')")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radios: list[int] = Field(default=[1000, 2000], description="Radios de análisis en metros")


class RingResult(BaseModel):
    radio_m: int
    competencia: int
    demanda_pob_30_59: float
    ism: float
    ism_banda: str
    fuente_demanda: str


class LocationAnalysisResponse(BaseModel):
    giro: str | None
    scian: str | None
    lat: float
    lon: float
    anillos: list[RingResult]
    tam_mxn: float
    tam_rango_mxn: tuple[float, float]
    huff_cuota_punto: float
    veredicto: str
    factores: list[str]
    advertencias: list[str]
    lineage: Lineage


class B2BRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radio_m: int = Field(default=5000, gt=0, le=50000)
    scian: list[str] = Field(default_factory=list, description="Clases SCIAN objetivo")
    estrato_min_ord: int = Field(default=5, ge=1, le=7)
    top_n: int = Field(default=50, ge=1, le=500)
    vertical: str = Field(default="climatizacion")


class B2BLeadResult(BaseModel):
    denue_id: str
    nombre: str
    scian_code: str
    estrato_texto: str
    distancia_m: float
    idt: float
    score: float
    desglose: dict[str, float]


class B2BResponse(BaseModel):
    total_candidatos: int
    leads: list[B2BLeadResult]
    lineage: Lineage


class LookalikeRequest(BaseModel):
    semillas: list[str] = Field(description="cvegeo de AGEB semilla")
    area_busqueda: str | None = Field(default=None, description="cve_ent o cvegeo de municipio")
    top_n: int = Field(default=10, ge=1, le=100)


class LookalikeItem(BaseModel):
    cvegeo: str
    similitud: float
    top_variables: list[str]


class LookalikeResponse(BaseModel):
    ranking: list[LookalikeItem]
    nota: str | None = None
    lineage: Lineage


# ------------------------------------------------------------ comparación --
class CompareRequest(BaseModel):
    """Comparación de investigaciones: entre 2 y 5 ids."""

    investigation_ids: list[UUID] = Field(
        min_length=2,
        max_length=5,
        description="Ids de las investigaciones a comparar (de 2 a 5)",
    )


class CompareItem(BaseModel):
    """Resumen comparable de una investigación (anillo de mayor radio)."""

    id: str
    nombre: str
    territorio: str
    center_lat: float | None = None
    center_lon: float | None = None
    veredicto: str
    ism: float
    competencia: int
    poblacion: float
    tam: float
    huff_score: float


class CompareResponse(BaseModel):
    items: list[CompareItem]
    lineage: Lineage
