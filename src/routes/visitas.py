from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends, UploadFile, File, Form, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.dependencies import get_session
from src.domain.schemas import VisitaCrear, VisitaSalida, DetalleVisitaCrear, DetalleVisitaSalida, VisitaConDetalleSalida
from src.services.servicio_visitas import ServicioVisitas
from src.config import settings
from src.errors import NotFoundError
router = APIRouter(prefix="/v1/visitas", tags=["visitas"])

@router.post("", response_model=VisitaSalida)
def crear_visita(
    payload: VisitaCrear,
    x_country: str | None = Header(default=None, alias=settings.COUNTRY_HEADER),
    db: Session = Depends(get_session),
):
    pais = (x_country or settings.DEFAULT_SCHEMA).lower()
    try:
        v = ServicioVisitas(db, pais).crear_visita(payload)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Ya existe una visita para ese cliente, vendedor y fecha")
    return v

@router.get("", response_model=list[VisitaSalida])
def listar_visitas(
    id_vendedor: str | None = None,
    d: date | None = None,
    x_country: str | None = Header(default=None, alias=settings.COUNTRY_HEADER),
    db: Session = Depends(get_session),
):
    pais = (x_country or settings.DEFAULT_SCHEMA).lower()
    return ServicioVisitas(db, pais).listar_visitas(id_vendedor=id_vendedor, d=d)

@router.post("/{id_visita}/detalle", response_model=DetalleVisitaSalida)
async def agregar_detalle(
    id_visita: str,
    id_cliente: str = Form(...),
    atendido_por: str | None = Form(None),
    hallazgos: str | None = Form(None),
    sugerencias_producto: str | None = Form(None),
    foto: UploadFile | None = File(None),
    x_country: str | None = Header(default=None, alias=settings.COUNTRY_HEADER),
    db: Session = Depends(get_session),
):
    pais = (x_country or settings.DEFAULT_SCHEMA).lower()

    payload = DetalleVisitaCrear(
        id_cliente=id_cliente,
        atendido_por=atendido_por,
        hallazgos=hallazgos,
        sugerencias_producto=sugerencias_producto,
    )

    contenido = await foto.read() if foto else None
    nombre = foto.filename if foto else None
    ctype = foto.content_type if foto else None
    try:
        detalle = ServicioVisitas(db, pais).agregar_detalle(
            id_visita,
            payload,
            foto_bytes=contenido,
            nombre_archivo=nombre,
            content_type=ctype,
        )
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Ya existe un detalle para esa visita")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return detalle


@router.get("/{id_visita}", response_model=VisitaConDetalleSalida)
def obtener_visita(
    id_visita: str,
    incluir_foto_ios: bool = True,
    x_country: str | None = Header(default=None, alias=settings.COUNTRY_HEADER),
    db: Session = Depends(get_session),
):
    pais = (x_country or settings.DEFAULT_SCHEMA).lower()
    try:
        visita, detalle, foto_ios = ServicioVisitas(db, pais).obtener_visita_con_detalle(id_visita)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # construir respuesta
    from src.domain.schemas import VisitaConDetalleSalida, DetalleVisitaSalida
    salida = VisitaConDetalleSalida(
        id=visita.id,
        id_vendedor=visita.id_vendedor,
        id_cliente=visita.id_cliente,
        direccion=visita.direccion,
        ciudad=visita.ciudad,
        contacto=visita.contacto,
        fecha=visita.fecha,
        estado=visita.estado,
        detalle=DetalleVisitaSalida.model_validate(detalle) if detalle else None,
        foto_ios=foto_ios if incluir_foto_ios else None,
    )
    return salida