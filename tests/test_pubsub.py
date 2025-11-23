import base64
import json
from datetime import date
from unittest.mock import patch, MagicMock, ANY

from src.config import settings


def _encode_event(event: dict) -> dict:
    """Helper para construir el envelope estándar de Pub/Sub."""
    raw = json.dumps(event).encode("utf-8")
    data_b64 = base64.b64encode(raw).decode("ascii")
    return {
        "message": {
            "data": data_b64,
            "messageId": "msg-1",
            "publishTime": "2025-10-21T00:00:00Z",
        },
        "subscription": "projects/test/subscriptions/sub-1",
    }


def test_pubsub_envelope_invalido(client):
    # request.json() lanza excepción → 204
    r = client.post("/pubsub", data="no-es-json", headers={"Content-Type": "application/json"})
    assert r.status_code == 204


def test_pubsub_sin_message(client):
    body = {"no_message": {}}
    r = client.post("/pubsub", json=body)
    assert r.status_code == 204


def test_pubsub_sin_data(client):
    body = {
        "message": {
            # sin 'data'
            "messageId": "msg-1",
            "publishTime": "2025-10-21T00:00:00Z",
        }
    }
    r = client.post("/pubsub", json=body)
    assert r.status_code == 204


def test_pubsub_data_malformed(client):
    # data es base64 pero el contenido no es JSON válido
    bad_raw = b"{no-json"
    data_b64 = base64.b64encode(bad_raw).decode("ascii")
    body = {
        "message": {
            "data": data_b64,
            "messageId": "msg-2",
            "publishTime": "2025-10-21T00:00:00Z",
        }
    }
    r = client.post("/pubsub", json=body)
    assert r.status_code == 204


def test_pubsub_event_sin_event_type(client):
    event = {
        # sin "event"
        "ctx": {"country": "co", "trace_id": "t-1"},
    }
    body = _encode_event(event)
    r = client.post("/pubsub", json=body)
    assert r.status_code == 204


def test_pubsub_event_tipo_desconocido(client):
    event = {
        "event": "otro_evento_que_no_manejamos",
        "ctx": {"country": "co", "trace_id": "t-2"},
    }
    body = _encode_event(event)
    r = client.post("/pubsub", json=body)
    # No debería fallar: simplemente no hace nada
    assert r.status_code == 204


@patch("src.routes.pubsub.session_for_schema")
@patch("src.routes.pubsub.ServicioPlanDeVentas")
def test_pubsub_recalcular_plan_ok(
    mock_svc_cls,
    mock_session_for_schema,
    client,
    headers,
    monkeypatch,
):
    # Aseguramos que el DEFAULT_SCHEMA sea consistente con los tests
    monkeypatch.setattr(
        settings,
        "DEFAULT_SCHEMA",
        headers.get(settings.COUNTRY_HEADER, "co"),
    )

    # Configurar session_for_schema para que NO toque la BD real
    fake_session = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = fake_session
    cm.__exit__.return_value = False
    mock_session_for_schema.return_value = cm

    # Mock del servicio de planes
    mock_svc = mock_svc_cls.return_value
    fake_plan = MagicMock()
    mock_svc.obtener.return_value = fake_plan

    event = {
        "event": "recalcular_plan_ventas",
        "plan_id": "PLAN-1",
        "fecha": "2025-10-21",
        "ctx": {
            "country": headers.get(settings.COUNTRY_HEADER, "co"),
            "trace_id": "trace-123",
        },
    }
    body = _encode_event(event)

    r = client.post("/pubsub", json=body)
    assert r.status_code == 204

    # Se debe haber creado el servicio con una sesión y el country correcto
    mock_svc_cls.assert_called_once()
    args_ctor, _ = mock_svc_cls.call_args
    assert len(args_ctor) == 2
    assert args_ctor[0] is fake_session
    assert args_ctor[1] == event["ctx"]["country"]

    mock_svc.obtener.assert_called_once_with("PLAN-1")
    mock_svc.recalcular_para_fecha.assert_called_once()
    args_recalc, _ = mock_svc.recalcular_para_fecha.call_args
    assert args_recalc[0] is fake_plan
    assert args_recalc[1] == date(2025, 10, 21)

def test_pubsub_recalcular_plan_sin_plan_id_negocio(client):
    # Este test asume que en tu handler haces:
    # if not plan_id: raise ValueError(...)
    event = {
        "event": "recalcular_plan_ventas",
        # sin "plan_id"
        "fecha": "2025-10-21",
        "ctx": {"country": "co"},
    }
    body = _encode_event(event)
    r = client.post("/pubsub", json=body)
    # Por diseño: aunque ValueError se loguea, siempre devolvemos 204
    assert r.status_code == 204


@patch("src.routes.pubsub.session_for_schema")
@patch("src.routes.pubsub.ServicioPlanDeVentas")
def test_pubsub_recalcular_plan_no_encontrado_lanza_value_error(
    mock_svc_cls,
    mock_session_for_schema,
    client,
):
    fake_session = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = fake_session
    cm.__exit__.return_value = False
    mock_session_for_schema.return_value = cm

    mock_svc = mock_svc_cls.return_value
    mock_svc.obtener.return_value = None  # Plan no existe

    event = {
        "event": "recalcular_plan_ventas",
        "plan_id": "NO-EXISTE",
        "fecha": "2025-10-21",
        "ctx": {"country": "co"},
    }
    body = _encode_event(event)
    r = client.post("/pubsub", json=body)
    assert r.status_code == 204


@patch("src.routes.pubsub.session_for_schema")
@patch("src.routes.pubsub.ServicioPlanDeVentas")
def test_pubsub_recalcular_plan_error_inesperado(
    mock_svc_cls,
    mock_session_for_schema,
    client,
):
    fake_session = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = fake_session
    cm.__exit__.return_value = False
    mock_session_for_schema.return_value = cm

    mock_svc = mock_svc_cls.return_value
    fake_plan = MagicMock()
    mock_svc.obtener.return_value = fake_plan
    mock_svc.recalcular_para_fecha.side_effect = RuntimeError("Fallo inesperado")

    event = {
        "event": "recalcular_plan_ventas",
        "plan_id": "PLAN-ERR",
        "fecha": "2025-10-21",
        "ctx": {"country": "co"},
    }
    body = _encode_event(event)
    r = client.post("/pubsub", json=body)
    assert r.status_code == 204