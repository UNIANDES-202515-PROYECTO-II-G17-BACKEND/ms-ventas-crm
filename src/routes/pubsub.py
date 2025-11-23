import logging
import json
import base64
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Request, Response
from src.config import settings
from src.infrastructure.infrastructure import session_for_schema
from src.services.servicio_plan_ventas import ServicioPlanDeVentas


log = logging.getLogger(__name__)
router = APIRouter(prefix="/pubsub", tags=["pubSub"])

@router.post("", status_code=204)
async def handle_pubsub_push(request: Request):
    """
    Handler para push de Pub/Sub.

    Siempre debe responder 204 (No Content) para evitar reintentos infinitos,
    incluso si hay errores de negocio o errores inesperados. Esos errores se
    registran en logs, pero la respuesta HTTP sigue siendo 204.
    """
    log_prefix = "[/pubsub]"

    # 1) Leer cuerpo JSON del request
    try:
        envelope = await request.json()
    except Exception as e:
        log.warning("%s Body inválido (no es JSON): %s", log_prefix, e)
        return Response(status_code=204)

    message = envelope.get("message")
    if not isinstance(message, dict):
        log.warning("%s Envelope sin 'message': %s", log_prefix, envelope)
        return Response(status_code=204)

    data_b64 = message.get("data")
    if not data_b64:
        log.warning("%s Mensaje sin 'data': %s", log_prefix, message)
        return Response(status_code=204)

    # 2) Decodificar base64 + JSON del evento
    try:
        payload_bytes = base64.b64decode(data_b64)
        event = json.loads(payload_bytes)
    except Exception as e:
        log.warning("%s 'data' no es JSON válido: %s", log_prefix, e)
        return Response(status_code=204)

    event_type = event.get("event")
    if not event_type:
        log.warning("%s Evento sin campo 'event': %s", log_prefix, event)
        return Response(status_code=204)

    ctx = event.get("ctx") or {}
    trace_id = ctx.get("trace_id")
    country = ctx.get("country") or settings.DEFAULT_SCHEMA

    if trace_id:
        log_prefix = f"[/pubsub trace_id={trace_id}]"

    log.info("%s Evento recibido: %s (country=%s)", log_prefix, event_type, country)

    try:
        # =====================================================================
        # 3) Evento: recálculo de plan de ventas
        # =====================================================================
        if event_type == "recalcular_plan_ventas":
            plan_id = event.get("plan_id")
            if not plan_id:
                raise ValueError("plan_id es obligatorio en recalcular_plan_ventas")

            fecha_str = event.get("fecha")
            try:
                fecha = date.fromisoformat(fecha_str) if fecha_str else date.today()
            except Exception:
                raise ValueError(f"Fecha inválida en evento recalcular_plan_ventas: {fecha_str!r}")

            log.info(
                "%s Iniciando recálculo de plan de ventas. plan_id=%s fecha=%s",
                log_prefix,
                plan_id,
                fecha,
            )

            # Abrimos sesión con el schema adecuado y llamamos al servicio
            with session_for_schema(country) as session:
                svc = ServicioPlanDeVentas(session, country)
                plan = svc.obtener(plan_id)
                if not plan:
                    raise ValueError(f"Plan de ventas no encontrado. id={plan_id}")

                prog = svc.recalcular_para_fecha(plan, fecha)

                log.info(
                    "%s Recalculo completado. plan_id=%s fecha=%s monto=%s unidades=%s clientes=%s pedidos=%s",
                    log_prefix,
                    plan_id,
                    fecha,
                    prog.monto_actual,
                    prog.unidades_actuales,
                    prog.clientes_actuales,
                    prog.pedidos_contados,
                )

        # =====================================================================
        # 4) Otros tipos de evento (de momento, ignorados)
        # =====================================================================
        else:
            log.info("%s Evento %s ignorado (no hay handler definido)", log_prefix, event_type)

    except ValueError as e:
        # Error de negocio → NO reintentar
        log.warning("%s Error de negocio en %s: %s", log_prefix, event_type, e)

    except Exception as e:
        # Error inesperado → igual devolvemos 204 para evitar loops infinitos
        log.error("%s Error procesando %s: %s", log_prefix, event_type, e)

    log.debug("%s Handler /pubsub completado", log_prefix)
    return Response(status_code=204)