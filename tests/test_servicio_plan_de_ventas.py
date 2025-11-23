from unittest.mock import patch, MagicMock
from datetime import date
from decimal import Decimal
from src.services.servicio_plan_ventas import ServicioPlanDeVentas
from src.domain import models

# Helper para crear un plan en la DB de prueba
def _crear_plan_basico(db):
    plan = models.PlanDeVentas(
        id="PLAN-1",
        id_vendedor="VEN-1",
        periodo="mensual",
        territorio="Norte",
        meta_monto=1000,
        meta_unidades=10,
        meta_clientes=1,
        fecha_inicio=date(2025,1,1),
        fecha_fin=date(2025,12,31),
        id_cliente_objetivo="CLI-1",
        activo=True
    )
    db.add(plan)
    db.flush()
    return plan


def test_recalcular_sin_productos(db_session):
    plan = _crear_plan_basico(db_session)  # sin productos

    svc = ServicioPlanDeVentas(db_session, "co")

    prog = svc.recalcular_para_fecha(plan, date(2025,10,21))

    assert prog.monto_actual == Decimal("0")
    assert prog.unidades_actuales == 0
    assert prog.clientes_actuales == 0
    assert prog.pedidos_contados == 0


@patch("src.services.servicio_plan_ventas.MsClient")
def test_recalcular_vendedor_incorrecto(mock_client_cls, db_session):
    plan = _crear_plan_basico(db_session)
    # Agregar un producto
    plan.productos.append(models.PlanDeVentasProducto(id_producto="P1"))

    # Mock pedidos
    mock_inst = mock_client_cls.return_value
    mock_inst.get.return_value = [
        {
            "vendedor_id": "OTRO-VEND",
            "cliente_id": "CLI-1",
            "items": [
                {"producto_id": "P1", "cantidad": 1, "precio_unitario": 100,
                 "descuento_pct": 0, "impuesto_pct": 0}
            ]
        }
    ]

    svc = ServicioPlanDeVentas(db_session, "co")
    prog = svc.recalcular_para_fecha(plan, date(2025,10,21))

    # Se ignora → todo queda en cero
    assert prog.pedidos_contados == 0


@patch("src.services.servicio_plan_ventas.MsClient")
def test_recalcular_cliente_incorrecto(mock_client_cls, db_session):
    plan = _crear_plan_basico(db_session)
    plan.productos.append(models.PlanDeVentasProducto(id_producto="P1"))

    mock_inst = mock_client_cls.return_value
    mock_inst.get.return_value = [
        {
            "vendedor_id": "VEN-1",
            "cliente_id": "OTRO-CLI",
            "items": [{"producto_id": "P1", "cantidad": 1, "precio_unitario": 100,
                       "descuento_pct": 0, "impuesto_pct": 0}]
        }
    ]

    svc = ServicioPlanDeVentas(db_session, "co")
    prog = svc.recalcular_para_fecha(plan, date(2025,10,21))

    assert prog.pedidos_contados == 0


@patch("src.services.servicio_plan_ventas.MsClient")
def test_recalcular_sin_items_del_plan(mock_client_cls, db_session):
    plan = _crear_plan_basico(db_session)
    plan.productos.append(models.PlanDeVentasProducto(id_producto="P1"))

    mock_inst = mock_client_cls.return_value
    mock_inst.get.return_value = [
        {
            "vendedor_id": "VEN-1",
            "cliente_id": "CLI-1",
            "items": [
                {"producto_id": "NO-PLAN", "cantidad": 1, "precio_unitario": 100,
                 "descuento_pct": 0, "impuesto_pct": 0}
            ]
        }
    ]

    svc = ServicioPlanDeVentas(db_session, "co")
    prog = svc.recalcular_para_fecha(plan, date(2025,10,21))

    assert prog.pedidos_contados == 0


@patch("src.services.servicio_plan_ventas.MsClient")
def test_recalcular_con_items_validos(mock_client_cls, db_session):
    plan = _crear_plan_basico(db_session)
    plan.productos.append(models.PlanDeVentasProducto(id_producto="P1"))

    mock_inst = mock_client_cls.return_value
    mock_inst.get.return_value = [
        {
            "vendedor_id": "VEN-1",
            "cliente_id": "CLI-1",
            "items": [
                {"producto_id": "P1", "cantidad": 2, "precio_unitario": 100,
                 "descuento_pct": 10, "impuesto_pct": 19}
            ]
        }
    ]

    svc = ServicioPlanDeVentas(db_session, "co")
    prog = svc.recalcular_para_fecha(plan, date(2025,10,21))

    assert prog.pedidos_contados == 1
    assert prog.unidades_actuales == 2
    assert prog.clientes_actuales == 1
    # Monto = 100*2 * (1-0.10) * (1+0.19) = 238
    assert prog.monto_actual == Decimal("214.2")
