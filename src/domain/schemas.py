from __future__ import annotations
from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field


class PlanDeVentasCrear(BaseModel):
    id_vendedor: str
    periodo: str = Field(default="mensual")
    territorio: Optional[str] = None
    meta_monto: Optional[float] = None
    meta_unidades: Optional[int] = None
    meta_clientes: Optional[int] = None
    fecha_inicio: date
    fecha_fin: date
    ids_productos: List[str] = Field(default_factory=list)
    id_cliente_objetivo: str


class PlanDeVentasSalida(BaseModel):
    id: str
    id_vendedor: str
    periodo: str
    territorio: Optional[str]
    meta_monto: Optional[float]
    meta_unidades: Optional[int]
    meta_clientes: Optional[int]
    fecha_inicio: date
    fecha_fin: date
    activo: bool
    ids_productos: List[str] = []
    id_cliente_objetivo: str

    class Config:
        from_attributes = True


class ProgresoSalida(BaseModel):
    fecha: date
    monto_actual: float
    unidades_actuales: int
    clientes_actuales: int
    pedidos_contados: int

    class Config:
        from_attributes = True


# --- Visitas (Pydantic) ---------------------------------------------------------
class VisitaCrear(BaseModel):
    id_vendedor: str
    id_cliente: str
    direccion: str
    ciudad: str
    contacto: str
    fecha: date


class VisitaSalida(BaseModel):
    id: str
    id_vendedor: str
    id_cliente: str
    direccion: str
    ciudad: str
    contacto: str
    fecha: date
    estado: str

    class Config:
        from_attributes = True


class DetalleVisitaCrear(BaseModel):
    id_cliente: str
    atendido_por: Optional[str] = None
    hallazgos: Optional[str] = None
    sugerencias_producto: Optional[str] = None


class DetalleVisitaSalida(BaseModel):
    id: int
    id_visita: str
    id_cliente: str
    atendido_por: Optional[str]
    hallazgos: Optional[str]
    sugerencias_producto: Optional[str]
    url_foto: Optional[str]

    class Config:
        from_attributes = True


class VisitaConDetalleSalida(BaseModel):
    id: str
    id_vendedor: str
    id_cliente: str
    direccion: str
    ciudad: str
    contacto: str
    fecha: date
    estado: str
    detalle: Optional[DetalleVisitaSalida] = None
    # data URI base64 para iOS (si se pudo obtener)
    foto_ios: Optional[str] = None

    class Config:
        from_attributes = True