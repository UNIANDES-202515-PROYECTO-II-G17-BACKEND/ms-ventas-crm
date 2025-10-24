from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Date, DateTime, Numeric, ForeignKey, UniqueConstraint, Text, func, Boolean


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos."""
    pass

# --- Planes de Ventas -----------------------------------------------------------
class PlanDeVentas(Base):
    __tablename__ = "plan_de_ventas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_vendedor: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    periodo: Mapped[str] = mapped_column(String(16), nullable=False, default="mensual")  # mensual|trimestral|anual
    territorio: Mapped[Optional[str]] = mapped_column(String(80))

    meta_monto: Mapped[Optional[Numeric]] = mapped_column(Numeric(14, 2))  # $ meta dinero
    meta_unidades: Mapped[Optional[int]] = mapped_column(Integer)
    meta_clientes: Mapped[Optional[int]] = mapped_column(Integer)

    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)

    # ÚNICO cliente objetivo del plan
    id_cliente_objetivo: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    productos: Mapped[list["PlanDeVentasProducto"]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    progresos: Mapped[list["ProgresoPlanDeVentas"]] = relationship(back_populates="plan", cascade="all, delete-orphan")

    creado_en: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "id_vendedor", "id_cliente_objetivo", "periodo", "fecha_inicio", "fecha_fin",
            name="uq_plan_unico"
        ),
    )

class PlanDeVentasProducto(Base):
    __tablename__ = "plan_de_ventas_producto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_plan: Mapped[str] = mapped_column(ForeignKey("plan_de_ventas.id", ondelete="CASCADE"), index=True)
    id_producto: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    plan: Mapped["PlanDeVentas"] = relationship(back_populates="productos")

    __table_args__ = (
        UniqueConstraint("id_plan", "id_producto", name="uq_plan_producto"),
    )


class ProgresoPlanDeVentas(Base):
    __tablename__ = "progreso_plan_de_ventas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_plan: Mapped[str] = mapped_column(ForeignKey("plan_de_ventas.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)

    # métricas acumuladas al día
    monto_actual: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=0)
    unidades_actuales: Mapped[int] = mapped_column(Integer, default=0)
    clientes_actuales: Mapped[int] = mapped_column(Integer, default=0)
    pedidos_contados: Mapped[int] = mapped_column(Integer, default=0)

    plan: Mapped["PlanDeVentas"] = relationship(back_populates="progresos")


# --- Visitas --------------------------------------------------------------------
class Visita(Base):
    __tablename__ = "visita"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_vendedor: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    id_cliente: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    direccion: Mapped[str] = mapped_column(String(200), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(100), nullable=False)
    contacto: Mapped[str] = mapped_column(String(100), nullable=False)

    fecha: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    estado: Mapped[str] = mapped_column(String(16), default="pendiente")  # pendiente|finalizada

    detalles: Mapped[list["DetalleVisita"]] = relationship(back_populates="visita", cascade="all, delete-orphan")

    creado_en: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("id_cliente", "id_vendedor", "fecha", name="uq_visita_cliente_vendedor_fecha"),
    )


class DetalleVisita(Base):
    __tablename__ = "detalle_visita"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_visita: Mapped[str] = mapped_column(ForeignKey("visita.id", ondelete="CASCADE"), index=True)
    id_cliente: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    atendido_por: Mapped[Optional[str]] = mapped_column(String(120))
    hallazgos: Mapped[Optional[str]] = mapped_column(Text)
    sugerencias_producto: Mapped[Optional[str]] = mapped_column(Text)

    url_foto: Mapped[Optional[str]] = mapped_column(String(512))  # GCS public/signed URL
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    visita: Mapped["Visita"] = relationship(back_populates="detalles")

    __table_args__ = (
        UniqueConstraint("id_visita", name="uq_detalle_visita_unico"),
    )