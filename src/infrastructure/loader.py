from __future__ import annotations

import uuid
from typing import Tuple
from datetime import timedelta

from google.cloud import storage

from src.config import settings


class CargadorGCS:
    """
    En producción (Cloud Run) usa ADC y el SA del servicio.
    - Guardamos/recuperamos por 'ruta_objeto' (clave dentro del bucket).
    - Podemos generar URL firmadas v4 cuando haga falta.
    - Podemos descargar bytes + content-type para responder como data URI en iOS.
    """

    def __init__(self, pais: str):
        self.nombre_bucket = f"{settings.GCS_BUCKET_PREFIX}-{pais.lower()}"
        self.cliente = storage.Client()
        self.bucket = self.cliente.bucket(self.nombre_bucket)

    # ---------- Escritura ----------

    def _ruta_foto_visita(self, id_visita: str, nombre_archivo: str) -> str:
        return f"visitas/{id_visita}/{uuid.uuid4().hex}-{nombre_archivo}"

    def subir_foto_visita(
        self,
        id_visita: str,
        nombre_archivo: str,
        datos: bytes,
        content_type: str,
    ) -> str:
        """
        Sube el archivo y retorna la RUTA (no URL). Ej.: 'visitas/<id>/<uuid>-img.jpg'
        Así luego podemos firmar/descargar según convenga.
        """
        ruta = self._ruta_foto_visita(id_visita, nombre_archivo)
        blob = self.bucket.blob(ruta)
        blob.upload_from_string(datos, content_type=content_type)
        return ruta

    # ---------- Lectura ----------

    def url_firmada(self, ruta_objeto: str, minutos: int = 15, method: str = "GET") -> str:
        """
        Genera una URL firmada v4 temporal para ese objeto.
        """
        blob = self.bucket.blob(ruta_objeto)
        return blob.generate_signed_url(
            version="v4",
            method=method,
            expiration=timedelta(minutes=minutos),
            response_disposition="inline",
        )

    def descargar_bytes_y_tipo(self, ruta_objeto: str) -> Tuple[bytes, str]:
        """
        Descarga el objeto como bytes y devuelve (bytes, content_type).
        """
        blob = self.bucket.blob(ruta_objeto)
        data = blob.download_as_bytes()
        ctype = blob.content_type or "application/octet-stream"
        return data, ctype