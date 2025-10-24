from __future__ import annotations
import uuid
from typing import Optional
from google.cloud import storage
from src.config import settings


class CargadorGCS:
    def __init__(self, pais: str):
        self.nombre_bucket = f"{settings.GCS_BUCKET_PREFIX}-{pais.lower()}"
        self.cliente = storage.Client()
        self.bucket = self.cliente.bucket(self.nombre_bucket)

    def subir_foto_visita(self, id_visita: str, nombre_archivo: str, datos: bytes, content_type: str) -> str:
        clave = f"visitas/{id_visita}/{uuid.uuid4().hex}-{nombre_archivo}"
        blob = self.bucket.blob(clave)
        blob.upload_from_string(datos, content_type=content_type)
        return blob.public_url

