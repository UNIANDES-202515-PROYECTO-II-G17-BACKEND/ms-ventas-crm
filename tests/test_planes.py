from unittest.mock import patch

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
    assert r2.status_code in (400, 409)

@patch("src.infrastructure.http.MsClient.get")
def test_recalcular_plan_filtra_por_producto_y_cliente(mock_get, client, headers):
    payload = {
        "id_vendedor": "seller-2",
        "periodo": "mensual",
        "territorio": "Zona Sur",
        "meta_monto": 5000.0,
        "meta_unidades": 20,
        "meta_clientes": 1,
        "fecha_inicio": "2025-10-01",
        "fecha_fin": "2025-10-31",
        # << SOLO el producto que debe aportar >>
        "ids_productos": ["P-OK"],
        "id_cliente_objetivo": "CLI-OK",
    }
    r = client.post("/v1/ventas/planes", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    plan_id = r.json()["id"]

    mock_get.return_value = [
        {
            "vendedor_id": "seller-2",
            "cliente_id": "CLI-OK",
            "items": [
                {"producto_id": "P-OK", "cantidad": 2, "precio_unitario": 100, "descuento_pct": 0, "impuesto_pct": 0},
                {"producto_id": "P-IGN", "cantidad": 5, "precio_unitario": 10, "descuento_pct": 0, "impuesto_pct": 0},
            ],
        }
    ]
    d = "2025-10-21"
    r2 = client.post(f"/v1/ventas/planes/{plan_id}/recalcular?d={d}", headers=headers)
    body = r2.json()

    # Solo debe sumar el ítem de P-OK
    assert body["unidades_actuales"] == 2
    assert float(body["monto_actual"]) == 200.0
    assert body["clientes_actuales"] == 1
    assert body["pedidos_contados"] == 1