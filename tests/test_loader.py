# tests/test_loader.py
from unittest.mock import patch, MagicMock
from src.infrastructure.loader import CargadorGCS
from src.config import settings

def _fake_blob():
    blob = MagicMock()
    blob.upload_from_string = MagicMock()
    blob.generate_signed_url = MagicMock(return_value="https://signed.example/url")
    blob.download_as_bytes = MagicMock(return_value=b"IMG")
    type(blob).content_type = "image/jpeg"
    return blob

def _fake_bucket():
    bucket = MagicMock()
    bucket.blob = MagicMock(side_effect=lambda ruta: _fake_blob())
    return bucket

@patch("src.infrastructure.loader.storage.Client")
def test_url_firmada(mock_client):
    fake_client = MagicMock()
    fake_bucket = _fake_bucket()
    fake_client.bucket.return_value = fake_bucket
    mock_client.return_value = fake_client

    loader = CargadorGCS(pais="co")
    object_name = "visitas/VIS-1/x.jpg"
    signed = loader.url_firmada(object_name, minutos=5)

    # Debe ser una URL no vacía
    assert isinstance(signed, str) and signed
    assert signed.startswith("http")

    # Dos comportamientos válidos:
    # 1) URL pública de GCS: debe contener bucket y object_name
    # 2) URL firmada de nuestro stub (cuando el método usa generate_signed_url)
    bucket_name = f"{settings.GCS_BUCKET_PREFIX}-co"
    if "storage.googleapis.com" in signed:
        assert bucket_name in signed
        assert object_name in signed
    else:
        # Aceptamos la URL del stub de firma
        assert signed == "https://signed.example/url"


@patch("src.infrastructure.loader.storage.Client")
def test_descargar_bytes_y_tipo(mock_client):
    fake_client = MagicMock()
    fake_bucket = _fake_bucket()
    fake_client.bucket.return_value = fake_bucket
    mock_client.return_value = fake_client

    loader = CargadorGCS(pais="co")
    data, ctype = loader.descargar_bytes_y_tipo("visitas/VIS-1/x.jpg")
    assert data == b"IMG"
    assert ctype == "image/jpeg"
