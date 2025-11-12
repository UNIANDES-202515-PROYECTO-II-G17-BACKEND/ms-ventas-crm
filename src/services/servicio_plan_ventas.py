from __future__ import annotations
from uuid import uuid4
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.domain import models
from src.domain.schemas import PlanDeVentasCrear
from src.infrastructure.http import MsClient  # Usa tu cliente existente
from decimal import Decimal

_MAX_LIMIT = 200


def _dec(v, d="0"):
    return Decimal(str(v if v is not None else d))


class ServicioPlanDeVentas:
    def __init__(self, db: Session, x_country: str):
        self.db = db
        self.client = MsClient(x_country)

    def crear(self, payload: PlanDeVentasCrear) -> models.PlanDeVentas:
        plan = models.PlanDeVentas(
            id=str(uuid4()),
            id_vendedor=payload.id_vendedor,
            periodo=payload.periodo,
            territorio=payload.territorio,
            meta_monto=payload.meta_monto,
            meta_unidades=payload.meta_unidades,
            meta_clientes=payload.meta_clientes,
            fecha_inicio=payload.fecha_inicio,
            fecha_fin=payload.fecha_fin,
            id_cliente_objetivo=payload.id_cliente_objetivo,
            activo=True,
        )
        for pid in payload.ids_productos:
            plan.productos.append(models.PlanDeVentasProducto(id_producto=pid))

        self.db.add(plan)
        self.db.flush()
        return plan

    def obtener(self, id_plan: str) -> models.PlanDeVentas | None:
        return self.db.get(models.PlanDeVentas, id_plan)

    def obtener_todos(self) -> list[models.PlanDeVentas]:
        return self.db.execute(select(models.PlanDeVentas)).scalars().all()

    def obtener_por_vendedor(self, id_vendedor: str) -> list[models.PlanDeVentas]:
        return self.db.execute(
            select(models.PlanDeVentas).where(models.PlanDeVentas.id_vendedor == id_vendedor)
        ).scalars().all()

    def recalcular_para_fecha(self, plan: models.PlanDeVentas, d: date) -> models.ProgresoPlanDeVentas:
        productos_set = {str(p.id_producto) for p in plan.productos}
        cliente_obj = str(plan.id_cliente_objetivo) if plan.id_cliente_objetivo is not None else None

        # Requiere productos definidos; si no, no aporta
        if not productos_set:
            # upsert progreso en 0 (útil para dejar registro del día)
            prog = (
                self.db.execute(
                    select(models.ProgresoPlanDeVentas).where(
                        models.ProgresoPlanDeVentas.id_plan == plan.id,
                        models.ProgresoPlanDeVentas.fecha == d,
                    )
                ).scalar_one_or_none()
            )
            if not prog:
                prog = models.ProgresoPlanDeVentas(id_plan=plan.id, fecha=d)
                self.db.add(prog)
            prog.monto_actual = Decimal("0")
            prog.unidades_actuales = 0
            prog.clientes_actuales = 0
            prog.pedidos_contados = 0
            self.db.flush()
            return prog

        # 1) Llamada al ms-pedidos: tipo VENTA + fecha_compromiso
        params = {
            "tipo": "VENTA",
            "fecha_compromiso": d.isoformat(),
            "limit": _MAX_LIMIT,
            "offset": 0,
        }
        pedidos = self.client.get("/v1/pedidos", params=params) or []

        monto = Decimal("0")
        unidades = 0
        clientes = set()
        pedidos_contados = 0

        for p in pedidos:
            # 2) Filtrar por vendedor del plan
            if str(p.get("vendedor_id")) != str(plan.id_vendedor):
                continue

            # 3) Validar cliente objetivo (obligatorio)
            if cliente_obj and str(p.get("cliente_id")) != cliente_obj:
                continue

            # 4) Ítems del pedido que pertenecen al plan (por producto)
            items_plan = []
            for item in p.get("items", []):
                if str(item.get("producto_id")) in productos_set:
                    items_plan.append(item)

            # Debe tener al menos un ítem del plan
            if not items_plan:
                continue

            # 5) Sumar monto y unidades solo de los ítems del plan
            total_pedido_aportado = Decimal("0")
            unidades_pedido_aportadas = 0

            for it in items_plan:
                cant = int(it.get("cantidad", 0))
                pu = _dec(it.get("precio_unitario"))
                dsc = _dec(it.get("descuento_pct")) / 100
                imp = _dec(it.get("impuesto_pct")) / 100

                linea = pu * cant
                neto = linea * (Decimal("1") - dsc)
                con_impuesto = neto * (Decimal("1") + imp)

                total_pedido_aportado += con_impuesto
                unidades_pedido_aportadas += cant

            if unidades_pedido_aportadas > 0:
                pedidos_contados += 1
                clientes.add(p.get("cliente_id"))
                monto += total_pedido_aportado
                unidades += unidades_pedido_aportadas

        # UPSERT progreso (id_plan, fecha)
        prog = (
            self.db.execute(
                select(models.ProgresoPlanDeVentas).where(
                    models.ProgresoPlanDeVentas.id_plan == plan.id,
                    models.ProgresoPlanDeVentas.fecha == d,
                )
            ).scalar_one_or_none()
        )
        if not prog:
            prog = models.ProgresoPlanDeVentas(id_plan=plan.id, fecha=d)
            self.db.add(prog)

        prog.monto_actual = monto
        prog.unidades_actuales = unidades
        prog.clientes_actuales = len(clientes)
        prog.pedidos_contados = pedidos_contados
        self.db.flush()
        return prog
