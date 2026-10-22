"""Esquemas Pydantic v2 del módulo de configuración inicial + IA interna."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- perfil
class EmpresaBlock(BaseModel):
    nombre: str = ""
    sitio_web: str = ""
    ubicacion_base: str = ""
    tamano_empleados: str = ""
    antiguedad_anos: str = ""


class VerticalBlock(BaseModel):
    id: str = ""
    giro_descripcion: str = ""


class ProductoBlock(BaseModel):
    nombre: str = ""
    descripcion: str = ""
    ticket_min_mxn: str = ""
    ticket_max_mxn: str = ""
    ciclo_venta_dias: str = ""
    margen_aprox_pct: str = ""


class ClienteIdealBlock(BaseModel):
    descripcion: str = ""
    tamano: str = ""
    puesto_decisor: str = ""
    dolores: str = ""


class ModeloComercialBlock(BaseModel):
    ticket_promedio_mxn: str = ""
    canales_contacto: str = ""
    ciclo_descripcion: str = ""


class TerritorioBlock(BaseModel):
    estados: str = ""
    ciudades: str = ""
    radio_km: str = ""


class EstacionalidadBlock(BaseModel):
    notas: str = ""


class CompanyProfile(BaseModel):
    """Espejo del bloque YAML de PERFIL-EMPRESA.md (todo opcional para
    aceptar también la plantilla sin llenar)."""

    empresa: EmpresaBlock = Field(default_factory=EmpresaBlock)
    vertical: VerticalBlock = Field(default_factory=VerticalBlock)
    productos: list[ProductoBlock] = Field(default_factory=list)
    cliente_ideal: ClienteIdealBlock = Field(default_factory=ClienteIdealBlock)
    propuesta_valor: str = ""
    diferenciadores: list[str] = Field(default_factory=list)
    competidores: list[str] = Field(default_factory=list)
    modelo_comercial: ModeloComercialBlock = Field(default_factory=ModeloComercialBlock)
    territorio: TerritorioBlock = Field(default_factory=TerritorioBlock)
    estacionalidad: EstacionalidadBlock = Field(default_factory=EstacionalidadBlock)
    objetivos: list[str] = Field(default_factory=list)
    vocabulario: dict[str, str] = Field(default_factory=dict)
    scian_sugeridos: list[str] = Field(default_factory=list)


# ------------------------------------------------- configuración derivada
class TamDefault(BaseModel):
    producto: str
    ticket_mxn: float = 0.0
    ciclo_dias: int = 0


class VerticalConfig(BaseModel):
    """Configuración operativa derivada del perfil: gobierna scoring,
    TAM, líneas de producto, outreach y vocabulario del ecosistema."""

    vertical_id: str = ""
    nombre_empresa: str = ""
    scian_targets: list[str] = Field(default_factory=list)
    demand_intensity: dict[str, float] = Field(default_factory=dict)
    scoring_weights: dict[str, float] = Field(default_factory=dict)
    tam_defaults: list[TamDefault] = Field(default_factory=list)
    line_rules: list[str] = Field(default_factory=list)
    outreach_channels: list[str] = Field(default_factory=list)
    vocabulary: dict[str, str] = Field(default_factory=dict)
    icp_keywords: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------ API
class ProfilePutBody(BaseModel):
    markdown: str


class ProfileOut(BaseModel):
    id: int
    vertical_id: str | None = None
    nombre: str | None = None
    version: int
    is_active: bool
    faltantes: list[str] = Field(default_factory=list)
    created_at: Any = None


class DeriveBody(BaseModel):
    markdown: str | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatBody(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class FillProfileBody(BaseModel):
    url: str | None = None
    text: str | None = None
    filename: str | None = None


class FactBody(BaseModel):
    key: str
    value: Any
    source: str = "manual"
    confidence: float = 1.0
