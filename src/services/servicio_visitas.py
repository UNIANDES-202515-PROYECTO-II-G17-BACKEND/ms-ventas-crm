from __future__ import annotations
from uuid import uuid4
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.domain import models
from src.domain.schemas import VisitaCrear, DetalleVisitaCrear
from src.infrastructure.loader import CargadorGCS
from src.config import settings
from src.errors import NotFoundError
import base64, requests

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

    def listar_visitas(self, id_vendedor: str | None = None, d: date | None = None):
        stmt = select(models.Visita)
        if id_vendedor:
            stmt = stmt.where(models.Visita.id_vendedor == id_vendedor)
        if d:
            stmt = stmt.where(models.Visita.fecha == d)
        return list(self.db.execute(stmt).scalars())

    # --- Obtener visita por id, con detalle y foto iOS (data URI) ---
    def obtener_visita_con_detalle(self, id_visita: str) -> tuple[models.Visita, models.DetalleVisita | None, str | None]:
        visita = self.db.get(models.Visita, id_visita)
        if not visita:
            raise ValueError("Visita no encontrada")

        # asumimos un solo detalle por la restricción de unicidad
        detalle = self.db.execute(
            select(models.DetalleVisita).where(models.DetalleVisita.id_visita == id_visita)
        ).scalar_one_or_none()

        foto_ios: str | None = None
        if detalle and detalle.url_foto:
            # Intentar descargar y codificar base64 (para dispositivos iOS)
            try:
                r = requests.get(detalle.url_foto, timeout=20)
                if r.ok and r.content:
                    b64 = base64.b64encode(r.content).decode("utf-8")
                    # asumimos jpeg por defecto; puedes detectar por cabecera si quieres
                    foto_ios = f"data:image/jpeg;base64,{b64}"
            except Exception:
                # si falla (privado o restricción), lo dejamos en None
                foto_ios = None

        return visita, detalle, foto_ios

    # --- Agregar o actualizar el detalle (upsert). Al guardar, finaliza la visita ---
    def agregar_detalle(
        self,
        id_visita: str,
        payload: DetalleVisitaCrear,
        *,
        foto_bytes: bytes | None = None,
        nombre_archivo: str | None = None,
        content_type: str | None = None
    ) -> models.DetalleVisita:
        visita = self.db.get(models.Visita, id_visita)
        if not visita:
            raise NotFoundError("Visita no encontrada")

        # buscar si ya existe un detalle para esa visita
        detalle = self.db.execute(
            select(models.DetalleVisita).where(models.DetalleVisita.id_visita == id_visita)
        ).scalar_one_or_none()

        if detalle:
            # actualizar
            detalle.id_cliente = payload.id_cliente
            detalle.atendido_por = payload.atendido_por
            detalle.hallazgos = payload.hallazgos
            detalle.sugerencias_producto = payload.sugerencias_producto
        else:
            # crear uno nuevo
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
            url = cargador.subir_foto_visita(
                id_visita,
                nombre_archivo or "foto.jpg",
                foto_bytes,
                content_type or "image/jpeg",
            )
            detalle.url_foto = url

        # Al guardar/actualizar el detalle, la visita queda finalizada
        visita.estado = "finalizada"
        self.db.flush()
        return detalle
