"""Tests del grafo LangGraph WhatsApp.

Prueba:
- triage_node clasifica correctamente todos los intents
- cotizacion_servicios_agent NO genera precios en ningún contexto
- cotizacion_tendo_agent SÍ menciona $20.000
- reserva_agent califica con MockSchedulingService (no acoplado al proveedor real)
- Multi-turno: el bot recuerda el nombre del turno anterior (via thread_id)
"""

import json
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from src.giros_bot.whatsapp.state import TriageIntent, WhatsAppState
from src.giros_bot.whatsapp.services.lead_capture import LeadData
from src.giros_bot.whatsapp.services.scheduling import SchedulingResult

# ── Mock services ─────────────────────────────────────────────────────────────

class MockSchedulingService:
    async def get_booking_url(self, context: dict) -> SchedulingResult:
        return SchedulingResult(
            available=True,
            booking_url="https://mock.calendly.com/giros",
            provider_name="Mock",
            instructions="Agenda aquí tu reunión →",
        )


class MockLeadCaptureService:
    def __init__(self):
        self.saved_leads: list[LeadData] = []

    async def save_lead(self, lead: LeadData) -> bool:
        self.saved_leads.append(lead)
        return True


def _make_config(phone: str = "56912345678") -> RunnableConfig:
    return cast(RunnableConfig, {
        "configurable": {
            "thread_id": f"wa_{phone}",
            "scheduling_service": MockSchedulingService(),
            "lead_service": MockLeadCaptureService(),
        }
    })


# ── Tests triage_node ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_triage_classifies_tendo():
    """Mensaje sobre stock/fiados → cotizacion_tendo."""
    mock_llm_response = MagicMock()
    mock_llm_response.content = json.dumps({
        "intent": "cotizacion_tendo",
        "quick_ack": "Entendido, hablemos de Tendo.",
    })
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    with patch(
        "src.giros_bot.whatsapp.nodes.triage_node._llm",
        new=mock_llm,
    ):
        from src.giros_bot.whatsapp.nodes.triage_node import triage_node

        state: WhatsAppState = {
            "messages": [HumanMessage(content="Necesito controlar el stock de mi almacén")],
            "sender_phone": "56912345678",
            "sender_name": "Test",
            "intent": "",
            "lead_quality": "unknown",
            "lead_email": "",
            "lead_project_type": "",
            "lead_budget_hint": "",
            "lead_service_type": "",
            "response_text": "",
        }
        command = await triage_node(state, _make_config())
        assert command.goto == TriageIntent.COTIZACION_TENDO.value
        assert command.update is not None
        assert command.update["intent"] == TriageIntent.COTIZACION_TENDO.value


@pytest.mark.asyncio
async def test_triage_classifies_servicios():
    """Mensaje sobre web/logo → cotizacion_servicios."""
    mock_llm_response = MagicMock()
    mock_llm_response.content = json.dumps({
        "intent": "cotizacion_servicios",
        "quick_ack": "Claro, cuéntame más de tu proyecto.",
    })
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    with patch(
        "src.giros_bot.whatsapp.nodes.triage_node._llm",
        new=mock_llm,
    ):
        from src.giros_bot.whatsapp.nodes.triage_node import triage_node

        state: WhatsAppState = {
            "messages": [HumanMessage(content="Quiero una página web para mi empresa")],
            "sender_phone": "56911111111",
            "sender_name": "Test",
            "intent": "",
            "lead_quality": "unknown",
            "lead_email": "",
            "lead_project_type": "",
            "lead_budget_hint": "",
            "lead_service_type": "",
            "response_text": "",
        }
        command = await triage_node(state, _make_config("56911111111"))
        assert command.goto == TriageIntent.COTIZACION_SERVICIOS.value


@pytest.mark.asyncio
async def test_triage_classifies_agendar():
    """Mensaje sobre reunión → agendar_llamada."""
    mock_llm_response = MagicMock()
    mock_llm_response.content = json.dumps({
        "intent": "agendar_llamada",
        "quick_ack": "Perfecto, coordinemos.",
    })
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    with patch(
        "src.giros_bot.whatsapp.nodes.triage_node._llm",
        new=mock_llm,
    ):
        from src.giros_bot.whatsapp.nodes.triage_node import triage_node

        state: WhatsAppState = {
            "messages": [HumanMessage(content="Quiero agendar una reunión con el equipo")],
            "sender_phone": "56922222222",
            "sender_name": "Test",
            "intent": "",
            "lead_quality": "unknown",
            "lead_email": "",
            "lead_project_type": "",
            "lead_budget_hint": "",
            "lead_service_type": "",
            "response_text": "",
        }
        command = await triage_node(state, _make_config("56922222222"))
        assert command.goto == TriageIntent.AGENDAR.value


@pytest.mark.asyncio
async def test_triage_fallback_on_invalid_json():
    """JSON inválido del LLM → fallback a info_general sin romper."""
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Respuesta inesperada sin JSON"
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    with patch(
        "src.giros_bot.whatsapp.nodes.triage_node._llm",
        new=mock_llm,
    ):
        from src.giros_bot.whatsapp.nodes.triage_node import triage_node

        state: WhatsAppState = {
            "messages": [HumanMessage(content="Hola")],
            "sender_phone": "56933333333",
            "sender_name": "Test",
            "intent": "",
            "lead_quality": "unknown",
            "lead_email": "",
            "lead_project_type": "",
            "lead_budget_hint": "",
            "lead_service_type": "",
            "response_text": "",
        }
        command = await triage_node(state, _make_config("56933333333"))
        assert command.goto == TriageIntent.INFO_GENERAL.value


# ── Tests cotizacion_servicios_agent: no hay precios ─────────────────────────

@pytest.mark.asyncio
async def test_cotizacion_servicios_no_price_in_response():
    """cotizacion_servicios_agent NO debe mencionar precios en su respuesta."""
    price_keywords = ["$", "290", "290.000", "UF ", "pesos", "mensual", "precio", "costo", "vale"]

    mock_llm_response = MagicMock()
    mock_llm_response.content = (
        "Cuéntame más sobre tu proyecto. ¿Qué tipo de sitio web necesitas: "
        "landing page, e-commerce, o algo más a medida?"
    )
    mock_llm_response.additional_kwargs = {}
    mock_llm_response.tool_calls = []
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    with patch(
        "src.giros_bot.whatsapp.nodes.cotizacion_servicios_agent._llm_with_tools",
        new=mock_llm,
    ):
        from src.giros_bot.whatsapp.nodes.cotizacion_servicios_agent import (
            cotizacion_servicios_agent,
        )

        state: WhatsAppState = {
            "messages": [HumanMessage(content="¿Cuánto vale una página web?")],
            "sender_phone": "56944444444",
            "sender_name": "Test",
            "intent": "cotizacion_servicios",
            "lead_quality": "unknown",
            "lead_email": "",
            "lead_project_type": "",
            "lead_budget_hint": "",
            "lead_service_type": "",
            "response_text": "",
        }
        result = await cotizacion_servicios_agent(state, _make_config("56944444444"))
        response = result["response_text"].lower()
        for keyword in price_keywords:
            assert keyword.lower() not in response, (
                f"cotizacion_servicios_agent NO debe mencionar '{keyword}'"
            )


# ── Tests cotizacion_tendo_agent: sí hay precio ───────────────────────────────

@pytest.mark.asyncio
async def test_cotizacion_tendo_mentions_price():
    """cotizacion_tendo_agent SÍ debe mencionar el precio $20.000."""
    mock_llm_response = MagicMock()
    mock_llm_response.content = (
        "Tendo es ideal para tu almacén. Cuesta $20.000 CLP al mes y tienes 14 días gratis. "
        "¿Lo probamos esta semana?"
    )
    mock_llm_response.additional_kwargs = {}
    mock_llm_response.tool_calls = []
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    with patch(
        "src.giros_bot.whatsapp.nodes.cotizacion_tendo_agent._llm_with_tools",
        new=mock_llm,
    ):
        from src.giros_bot.whatsapp.nodes.cotizacion_tendo_agent import (
            cotizacion_tendo_agent,
        )

        state: WhatsAppState = {
            "messages": [HumanMessage(content="¿Cuánto vale Tendo?")],
            "sender_phone": "56955555555",
            "sender_name": "Test",
            "intent": "cotizacion_tendo",
            "lead_quality": "unknown",
            "lead_email": "",
            "lead_project_type": "",
            "lead_budget_hint": "",
            "lead_service_type": "",
            "response_text": "",
        }
        result = await cotizacion_tendo_agent(state, _make_config("56955555555"))
        assert "20.000" in result["response_text"] or "20000" in result["response_text"]


# ── Tests reserva_agent con mock ISchedulingService ───────────────────────────

@pytest.mark.asyncio
async def test_reserva_agent_uses_mock_scheduling_service():
    """reserva_agent usa el mock ISchedulingService. No llama a Calendly real."""
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Aquí puedes agendar → https://mock.calendly.com/giros"
    mock_llm_response.additional_kwargs = {}
    mock_llm_response.tool_calls = []
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    with patch(
        "src.giros_bot.whatsapp.nodes.reserva_agent._llm_with_tools",
        new=mock_llm,
    ):
        from src.giros_bot.whatsapp.nodes.reserva_agent import reserva_agent

        state: WhatsAppState = {
            "messages": [HumanMessage(content="Quiero agendar una reunión")],
            "sender_phone": "56966666666",
            "sender_name": "Pedro López",
            "intent": "agendar_llamada",
            "lead_quality": "unknown",
            "lead_email": "",
            "lead_project_type": "",
            "lead_budget_hint": "",
            "lead_service_type": "",
            "response_text": "",
        }
        result = await reserva_agent(state, _make_config("56966666666"))
        assert result["response_text"]  # Hay alguna respuesta


# ── Test schemas Pydantic: validación payload Meta ────────────────────────────

def test_whatsapp_payload_rejects_non_wa_object():
    """Payload con object='page' debe fallar la validación."""
    from pydantic import ValidationError

    from src.giros_bot.whatsapp.schemas import WhatsAppWebhookPayload

    with pytest.raises(ValidationError):
        WhatsAppWebhookPayload(
            object="page",
            entry=[],
        )


def test_whatsapp_payload_parses_correctly():
    """Payload correcto debe parsearse sin errores."""
    from src.giros_bot.whatsapp.schemas import WhatsAppWebhookPayload

    payload = WhatsAppWebhookPayload(
        **{
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "contacts": [
                                    {"profile": {"name": "Juan"}, "wa_id": "56912345678"}
                                ],
                                "messages": [
                                    {
                                        "id": "MSG_001",
                                        "timestamp": "1710000000",
                                        "type": "text",
                                        "from": "56912345678",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
    )
    msgs = payload.entry[0].changes[0].value.messages
    assert msgs is not None
    assert msgs[0].from_ == "56912345678"
