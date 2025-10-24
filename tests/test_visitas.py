from unittest.mock import patch
import base64

def test_crear_visita_y_unicidad(client, headers):
    payload = {
        "id_vendedor": "seller-10",
        "id_cliente": "cli-10",
        "direccion": "Calle 1",
        "ciudad": "Bogotá",
        "contacto": "Laura",
        "fecha": "2025-10-22",
    }
    r1 = client.post("/v1/visitas", json=payload, headers=headers)
    r2 = client.post("/v1/visitas", json=payload, headers=headers)
    assert r2.status_code in (400, 409)

@patch("src.services.servicio_visitas.CargadorGCS")
def test_agregar_detalle_upsert_y_finaliza(mock_cls, client, headers):
    # Configura la instancia mock para que NO requiera ADC y devuelva URL
    mock_inst = mock_cls.return_value
    mock_inst.subir_foto_visita.return_value = "http://example.com/foto.jpg"

    payload = {
        "id_vendedor": "seller-11",
        "id_cliente": "cli-11",
        "direccion": "Calle 2",
        "ciudad": "Bogotá",
        "contacto": "Mateo",
        "fecha": "2025-10-23",
    }
    r1 = client.post("/v1/visitas", json=payload, headers=headers)
    visita_id = r1.json()["id"]

    data = {
        "id_cliente": "cli-11",
        "atendido_por": "Carlos",
        "hallazgos": "OK",
        "sugerencias_producto": "Lub A",
    }
    files = {"foto": ("f.jpg", b"IMG", "image/jpeg")}
    client.post(f"/v1/visitas/{visita_id}/detalle", data=data, files=files, headers=headers)

    r3 = client.get(f"/v1/visitas/{visita_id}", headers=headers)
    assert r3.json()["estado"] == "finalizada"
    assert r3.json()["detalle"]["url_foto"] == "http://example.com/foto.jpg"


@patch("src.services.servicio_visitas.CargadorGCS")
@patch("requests.get")
def test_obtener_visita_con_foto_ios(mock_req, mock_cls, client, headers):
    # Mock CargadorGCS para evitar ADC y devolver una URL pública
    mock_inst = mock_cls.return_value
    mock_inst.subir_foto_visita.return_value = "http://example.com/foto.jpg"

    # 1) Crear visita
    payload = {
        "id_vendedor": "seller-12",
        "id_cliente": "cli-12",
        "direccion": "Calle 3",
        "ciudad": "Bogotá",
        "contacto": "Nati",
        "fecha": "2025-10-24",
    }
    r1 = client.post("/v1/visitas", json=payload, headers=headers)
    assert r1.status_code == 200, r1.text
    visita_id = r1.json()["id"]

    # 2) Agregar detalle SUBIENDO un archivo para que se cree el registro con url_foto
    data = {
        "id_cliente": "cli-12",
        "atendido_por": "Ana",
        "hallazgos": "Prueba",
        "sugerencias_producto": "Lub B",
    }
    files = {"foto": ("f.jpg", b"BYTES", "image/jpeg")}
    r2 = client.post(f"/v1/visitas/{visita_id}/detalle", data=data, files=files, headers=headers)
    assert r2.status_code == 200, r2.text

    # 3) Mock de la descarga para iOS
    mock_req.return_value.ok = True
    mock_req.return_value.content = b"FAKEBYTES"

    # 4) Obtener la visita con la imagen formateada para iOS (data URI base64)
    r3 = client.get(f"/v1/visitas/{visita_id}?incluir_foto_ios=true", headers=headers)
    assert r3.status_code == 200, r3.text
    body = r3.json()
    assert body["estado"] == "finalizada"
    assert body["detalle"] is not None
    assert body["detalle"]["url_foto"] == "http://example.com/foto.jpg"
    assert body["foto_ios"].startswith("data:image/jpeg;base64,")

def test_obtener_visita_not_found(client, headers):
    r = client.get("/v1/visitas/no-existe", headers=headers)
    assert r.status_code == 404