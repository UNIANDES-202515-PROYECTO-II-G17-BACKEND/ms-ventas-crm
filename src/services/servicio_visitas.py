from __future__ import annotations

from uuid import uuid4
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain import models
from src.domain.schemas import VisitaCrear, DetalleVisitaCrear
from src.infrastructure.loader import CargadorGCS
from src.config import settings
from src.errors import NotFoundError

import base64


class ServicioVisitas:
    def __init__(self, db: Session, pais: str | None = None):
        self.db = db
        self.pais = (pais or settings.DEFAULT_SCHEMA).lower()

    # --- Crear visita (respeta unicidad por (cliente, vendedor, fecha)) ---
    def crear_visita(self, payload: VisitaCrear) -> models.Visita:
        visita = models.Visita(
            id=str(uuid4()),
            id_vendedor=payload.id_vendedor,
            id_cliente=payload.id_cliente,
            direccion=payload.direccion,
            ciudad=payload.ciudad,
            contacto=payload.contacto,
            fecha=payload.fecha,
            estado="pendiente",
        )
        self.db.add(visita)
        self.db.flush()
        return visita

    def listar_visitas(self, id_vendedor: Optional[str] = None, d: Optional[date] = None):
        stmt = select(models.Visita)
        if id_vendedor:
            stmt = stmt.where(models.Visita.id_vendedor == id_vendedor)
        if d:
            stmt = stmt.where(models.Visita.fecha == d)
        return list(self.db.execute(stmt).scalars())

    # --- Obtener visita por id, con detalle y foto en formato iOS (data URI) ---
    def obtener_visita_con_detalle(
        self, id_visita: str
    ) -> tuple[models.Visita, models.DetalleVisita | None, str | None]:
        visita = self.db.get(models.Visita, id_visita)
        if not visita:
            raise NotFoundError("Visita no encontrada")

        detalle = self.db.execute(
            select(models.DetalleVisita).where(models.DetalleVisita.id_visita == id_visita)
        ).scalar_one_or_none()

        foto_ios: str | None = None
        if detalle and detalle.url_foto:
            # Ahora 'url_foto' almacena la RUTA del objeto en GCS (no la URL).
            try:
                carg = CargadorGCS(self.pais)
                bytes_img, ctype = carg.descargar_bytes_y_tipo(detalle.url_foto)
                b64 = base64.b64encode(bytes_img).decode("utf-8")
                foto_ios = f"data:{ctype};base64,{b64}"
            except Exception:
                foto_ios = None

        return visita, detalle, foto_ios

    # --- Agregar/Actualizar detalle (upsert) y finalizar visita ---
    def agregar_detalle(
        self,
        id_visita: str,
        payload: DetalleVisitaCrear,
        *,
        foto_bytes: bytes | None = None,
        nombre_archivo: str | None = None,
        content_type: str | None = None,
    ) -> models.DetalleVisita:
        visita = self.db.get(models.Visita, id_visita)
        if not visita:
            raise NotFoundError("Visita no encontrada")

        detalle = self.db.execute(
            select(models.DetalleVisita).where(models.DetalleVisita.id_visita == id_visita)
        ).scalar_one_or_none()

        if detalle:
            # actualizar existente
            detalle.id_cliente = payload.id_cliente
            detalle.atendido_por = payload.atendido_por
            detalle.hallazgos = payload.hallazgos
            detalle.sugerencias_producto = payload.sugerencias_producto
        else:
            # crear nuevo
            detalle = models.DetalleVisita(
                id_visita=id_visita,
                id_cliente=payload.id_cliente,
                atendido_por=payload.atendido_por,
                hallazgos=payload.hallazgos,
                sugerencias_producto=payload.sugerencias_producto,
            )
            self.db.add(detalle)

        if foto_bytes:
            cargador = CargadorGCS(self.pais)
            # Subimos y almacenamos **la ruta del objeto**:
            ruta = cargador.subir_foto_visita(
                id_visita,
                nombre_archivo or "foto.jpg",
                foto_bytes,
                content_type or "image/jpeg",
            )
            detalle.url_foto = ruta  # guardamos ruta, no URL

        # Al guardar/actualizar detalle, la visita queda finalizada
        visita.estado = "finalizada"
        self.db.flush()
        return detalle
