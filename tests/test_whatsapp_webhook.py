"""Tests del webhook de WhatsApp (Capa 1 — FastAPI).

Prueba:
- Challenge GET correcto e incorrecto
- POST 200 inmediato (< tiempo de procesamiento)
- Deduplicación de mensajes
- Ignorar payloads sin mensajes de texto
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.giros_bot.main import app
from src.giros_bot.services.lead_capture import LeadData
from src.giros_bot.services.scheduling import SchedulingResult

# ── Mocks de servicios ────────────────────────────────────────────────────────

class MockMessagingService:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    async def send_text(self, recipient_id: str, text: str) -> bool:
        self.sent.append((recipient_id, text))
        return True

    async def mark_as_read(self, message_id: str) -> bool:
        return True


class MockSchedulingService:
    async def get_booking_url(self, context: dict) -> SchedulingResult:
        return SchedulingResult(True, "https://mock.calendly.com/test", "Mock", "Agenda aquí →")


class MockLeadCaptureService:
    def __init__(self):
        self.saved_leads: list[LeadData] = []

    async def save_lead(self, lead: LeadData) -> bool:
        self.saved_leads.append(lead)
        return True


class MockGraph:
    async def ainvoke(self, state: dict, config: dict) -> dict:
        return {"response_text": "Respuesta de prueba del bot.", "messages": []}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Cliente de prueba con servicios mockeados en app.state.

    Los mocks se asignan DESPUÉS de que el TestClient (y su lifespan) arrancan,
    para que no sean sobreescritos por el lifespan real de la app.
    init_db/close_db se mockean para evitar conflictos de event loop: el singleton
    _engine de history_db está atado al loop de pytest-asyncio, incompatible con
    el loop interno de TestClient/anyio.
    """
    mock_settings = MagicMock()
    mock_settings.whatsapp_verify_token = "test_token_123"
    mock_settings.scheduling_provider = "calendly"
    mock_settings.scheduling_url = "https://calendly.com/test"

    with (
        patch("src.giros_bot.main.init_db", new_callable=AsyncMock),
        patch("src.giros_bot.main.close_db", new_callable=AsyncMock),
        TestClient(app, raise_server_exceptions=False) as c,
    ):
        # Asignar DESPUÉS del lifespan para que no se sobreescriban
        app.state.settings = mock_settings
        app.state.messaging_service = MockMessagingService()
        app.state.scheduling_service = MockSchedulingService()
        app.state.lead_service = MockLeadCaptureService()
        app.state.whatsapp_graph = MockGraph()
        app.state.processed_message_ids = set()
        yield c


VALID_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "ENTRY_ID_123",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "contacts": [{"profile": {"name": "Juan Test"}, "wa_id": "56912345678"}],
                        "messages": [
                            {
                                "id": "MSG_001",
                                "timestamp": "1710000000",
                                "type": "text",
                                "from": "56912345678",
                                "text": {"body": "Hola, quiero info sobre sus servicios"},
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


# ── Tests challenge GET ───────────────────────────────────────────────────────

def test_webhook_verify_challenge_ok(client):
    """Challenge GET correcto → retorna el challenge como texto plano."""
    resp = client.get(
        "/v1/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "CHALLENGE_NONCE_XYZ",
            "hub.verify_token": "test_token_123",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "CHALLENGE_NONCE_XYZ"


def test_webhook_verify_wrong_token(client):
    """Token incorrecto → 403."""
    resp = client.get(
        "/v1/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "NONCE",
            "hub.verify_token": "token_incorrecto",
        },
    )
    assert resp.status_code == 403


def test_webhook_verify_wrong_mode(client):
    """Mode distinto de 'subscribe' → 403."""
    resp = client.get(
        "/v1/webhook/whatsapp",
        params={
            "hub.mode": "unsubscribe",
            "hub.challenge": "NONCE",
            "hub.verify_token": "test_token_123",
        },
    )
    assert resp.status_code == 403


# ── Tests POST mensajes ───────────────────────────────────────────────────────

def test_webhook_post_returns_200_immediately(client):
    """POST con payload válido → 200 inmediato."""
    resp = client.post("/v1/webhook/whatsapp", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_webhook_post_deduplication(client):
    """El mismo message_id procesado dos veces → segundo retorna 'duplicate'."""
    resp1 = client.post("/v1/webhook/whatsapp", json=VALID_PAYLOAD)
    assert resp1.json()["status"] == "accepted"

    resp2 = client.post("/v1/webhook/whatsapp", json=VALID_PAYLOAD)
    assert resp2.json()["status"] == "duplicate"


def test_webhook_post_no_messages(client):
    """Payload de status update (sin messages) → 'ignored'."""
    payload_status = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ENTRY",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [{"id": "MSG_ID", "status": "delivered"}],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    resp = client.post("/v1/webhook/whatsapp", json=payload_status)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_post_invalid_object_type(client):
    """Payload con object distinto de whatsapp_business_account → 422."""
    bad_payload = dict(VALID_PAYLOAD)
    bad_payload["object"] = "page"
    resp = client.post("/v1/webhook/whatsapp", json=bad_payload)
    assert resp.status_code == 422
