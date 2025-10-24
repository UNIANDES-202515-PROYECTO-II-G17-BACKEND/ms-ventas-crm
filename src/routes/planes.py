from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends, Header, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.dependencies import get_session
from src.domain.schemas import PlanDeVentasCrear, PlanDeVentasSalida, ProgresoSalida
from src.services.servicio_plan_ventas import ServicioPlanDeVentas
from src.config import settings


router = APIRouter(prefix="/v1/ventas/planes", tags=["ventas"])


@router.post("", response_model=PlanDeVentasSalida)
def crear_plan(
    payload: PlanDeVentasCrear,
    db: Session = Depends(get_session),
    x_country: str | None = Header(default=None, alias=settings.COUNTRY_HEADER),
):
    svc = ServicioPlanDeVentas(db, x_country or settings.DEFAULT_SCHEMA)
    try:
        plan = svc.crear(payload)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Ya existe un plan de ventas con ese vendedor, cliente y rango/periodo")

    return PlanDeVentasSalida(
        id=plan.id,
        id_vendedor=plan.id_vendedor,
        periodo=plan.periodo,
        territorio=plan.territorio,
        meta_monto=float(plan.meta_monto or 0),
        meta_unidades=plan.meta_unidades,
        meta_clientes=plan.meta_clientes,
        fecha_inicio=plan.fecha_inicio,
        fecha_fin=plan.fecha_fin,
        activo=plan.activo,
        ids_productos=[p.id_producto for p in plan.productos],
        id_cliente_objetivo=plan.id_cliente_objetivo,
    )


@router.get("/{id_plan}/progreso", response_model=list[ProgresoSalida])
def obtener_progreso(id_plan: str, db: Session = Depends(get_session)):
    from sqlalchemy import select
    from src.domain.models import ProgresoPlanDeVentas
    filas = db.execute(
        select(ProgresoPlanDeVentas)
        .where(ProgresoPlanDeVentas.id_plan == id_plan)
        .order_by(ProgresoPlanDeVentas.fecha)
    ).scalars()
    return list(filas)


@router.post("/{id_plan}/recalcular", response_model=ProgresoSalida)
def recalcular(
    id_plan: str,
    d: date | None = Query(default=None),
    db: Session = Depends(get_session),
    x_country: str | None = Header(default=None, alias=settings.COUNTRY_HEADER),
):
    svc = ServicioPlanDeVentas(db, x_country or settings.DEFAULT_SCHEMA)
    plan = svc.obtener(id_plan)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan de ventas no encontrado")
    prog = svc.recalcular_para_fecha(plan, d or date.today())
    return prog
