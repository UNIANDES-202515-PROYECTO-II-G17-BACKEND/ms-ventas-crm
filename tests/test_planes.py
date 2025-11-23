from unittest.mock import patch
from src.config import settings
from datetime import date

def test_crear_plan_unico_y_duplicado(client, headers):
    payload = {
        "id_vendedor": "seller-1",
        "periodo": "mensual",
        "territorio": "Zona Norte",
        "meta_monto": 100000.0,
        "meta_unidades": 50,
        "meta_clientes": 5,
        "fecha_inicio": "2025-10-01",
        "fecha_fin": "2025-10-31",
        "ids_productos": ["PROD-A", "PROD-B"],
        "id_cliente_objetivo": "CLI-123",
    }
    r1 = client.post("/v1/ventas/planes", json=payload, headers=headers)
    assert r1.status_code == 200, r1.text

    r2 = client.post("/v1/ventas/planes", json=payload, headers=headers)
    # Puede ser 400 o 409 según cómo dispares la unicidad
    assert r2.status_code in (400, 409)


@patch("src.routes.planes.publish_event")
def test_recalcular_plan_publica_evento_pubsub(mock_publish, client, headers, monkeypatch):
    # Configura un topic "fake" para pruebas
    monkeypatch.setattr(settings, "TOPIC_VENTAS_CRM", "projects/test/topics/ventas-crm")

    # 1) Crear plan
    payload = {
        "id_vendedor": "seller-2",
        "periodo": "mensual",
        "territorio": "Zona Sur",
        "meta_monto": 5000.0,
        "meta_unidades": 20,
        "meta_clientes": 1,
        "fecha_inicio": "2025-10-01",
        "fecha_fin": "2025-10-31",
        "ids_productos": ["P-OK"],
        "id_cliente_objetivo": "CLI-OK",
    }
    r = client.post("/v1/ventas/planes", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    plan_id = r.json()["id"]

    # 2) Llamar al endpoint de recálculo (ahora asíncrono vía Pub/Sub)
    d = "2025-10-21"
    r2 = client.post(f"/v1/ventas/planes/{plan_id}/recalcular?d={d}", headers=headers)

    assert r2.status_code == 202
    body = r2.json()
    assert body["plan_id"] == plan_id
    assert body["fecha"] == d
    assert "Recalculo de plan encolado" in body["detail"]

    # 3) Verificar que se haya publicado exactamente un evento
    mock_publish.assert_called_once()
    args, kwargs = mock_publish.call_args
    event_dict, topic_path = args

    assert topic_path == "projects/test/topics/ventas-crm"
    assert event_dict["event"] == "recalcular_plan_ventas"
    assert event_dict["plan_id"] == plan_id
    assert event_dict["fecha"] == d

    ctx = event_dict.get("ctx") or {}
    assert ctx.get("country") == headers.get(settings.COUNTRY_HEADER, settings.DEFAULT_SCHEMA)


@patch("src.routes.planes.publish_event")
def test_recalcular_plan_sin_fecha_usa_hoy(mock_publish, client, headers, monkeypatch):
    monkeypatch.setattr(settings, "TOPIC_VENTAS_CRM", "projects/test/topics/ventas-crm")

    payload = {
        "id_vendedor": "seller-3",
        "periodo": "mensual",
        "territorio": "Zona Oeste",
        "meta_monto": 1000.0,
        "meta_unidades": 5,
        "meta_clientes": 1,
        "fecha_inicio": "2025-10-01",
        "fecha_fin": "2025-10-31",
        "ids_productos": ["P-OK"],
        "id_cliente_objetivo": "CLI-OK",
    }
    r = client.post("/v1/ventas/planes", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    plan_id = r.json()["id"]

    r2 = client.post(f"/v1/ventas/planes/{plan_id}/recalcular", headers=headers)
    assert r2.status_code == 202

    mock_publish.assert_called_once()
    event_dict, topic_path = mock_publish.call_args[0]

    # Fecha debe ser "hoy" en isoformat
    assert event_dict["fecha"] == date.today().isoformat()
    assert event_dict["plan_id"] == plan_id


def test_recalcular_plan_not_found(client, headers, monkeypatch):
    # Si TOPIC no está configurado, no debería importar para el 404
    fake_id = "no-existe"
    r = client.post(f"/v1/ventas/planes/{fake_id}/recalcular", headers=headers)
    assert r.status_code == 404
    body = r.json()
    assert body["detail"] == "Plan de ventas no encontrado"