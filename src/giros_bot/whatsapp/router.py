"""Router WhatsApp Business — Capa 1 (API / Webhook).

Endpoints:
  GET  /v1/webhook/whatsapp  → Validación del challenge de Meta (subscribe)
  POST /v1/webhook/whatsapp  → Recepción de mensajes. Responde 200 < 200ms,
                               procesa en BackgroundTask.

Patrón:
  - El handler POST valida el payload y dispara la BackgroundTask de inmediato.
  - La tarea invoca el grafo LangGraph, obtiene response_text y lo envía por WhatsApp.
  - Anti-duplicados: set en app.state para descartar message_id ya procesados.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .schemas import WhatsAppWebhookPayload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhook", tags=["WhatsApp"])


# ── Endpoint de debug: conversación síncrona (NO para producción) ─────────────

class _ChatDebugRequest(BaseModel):
    text: str = Field(..., description="Mensaje del usuario simulado.", examples=["Quiero una página web para mi negocio"])
    phone: str = Field(default="56900000000", description="Teléfono del usuario (simula el wa_id de WhatsApp).")
    name: str = Field(default="Test User", description="Nombre del usuario simulado.")
    thread_id: str | None = Field(default=None, description="ID de hilo para mantener contexto entre turnos. Si no se envía se usa wa_{phone}.")


class _ChatDebugResponse(BaseModel):
    thread_id: str
    intent: str
    response_text: str
    lead_quality: str


@router.post(
    "/whatsapp/chat",
    response_model=_ChatDebugResponse,
    tags=["WhatsApp · Debug"],
    summary="💬 Chat síncrono (SOLO DEV) — simula una conversación con el agente",
    description=(
        "**Endpoint exclusivo para desarrollo y pruebas.**\n\n"
        "Envía un mensaje de texto simulado al grafo LangGraph y retorna la respuesta "
        "del agente de forma síncrona (sin enviar nada a WhatsApp real).\n\n"
        "Permite probar el flujo completo de triage + agentes desde Swagger UI. "
        "Usa el mismo `phone` en llamadas sucesivas para mantener el contexto del hilo."
    ),
)
async def chat_debug(request: Request, body: _ChatDebugRequest) -> _ChatDebugResponse:
    """Invoca el grafo WhatsApp sincrónicamente y retorna la respuesta del agente."""
    whatsapp_graph = request.app.state.whatsapp_graph
    scheduling_service = request.app.state.scheduling_service
    lead_service = request.app.state.lead_service

    thread_id = body.thread_id or f"wa_{body.phone}"

    initial_state: dict = {
        "messages": [{"role": "user", "content": body.text}],
        "sender_phone": body.phone,
        "sender_name": body.name,
        "intent": "",
        "lead_quality": "unknown",
        "lead_email": "",
        "lead_project_type": "",
        "lead_budget_hint": "",
        "lead_service_type": "",
        "response_text": "",
    }

    try:
        result = await whatsapp_graph.ainvoke(
            initial_state,
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "scheduling_service": scheduling_service,
                    "lead_service": lead_service,
                }
            },
        )
    except Exception as e:
        logger.exception("Error en chat_debug: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    response_text = result.get("response_text", "")
    if not response_text:
        messages = result.get("messages", [])
        if messages:
            raw = messages[-1].content
            response_text = raw if isinstance(raw, str) else " ".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in raw
            ) if isinstance(raw, list) else str(raw)
        else:
            response_text = "(sin respuesta)"

    return _ChatDebugResponse(
        thread_id=thread_id,
        intent=result.get("intent", ""),
        response_text=response_text,
        lead_quality=result.get("lead_quality", "unknown"),
    )


# ── GET: challenge Meta ───────────────────────────────────────────────────────

@router.get("/whatsapp", response_class=PlainTextResponse)
async def whatsapp_verify(
    request: Request,
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
) -> str:
    """Endpoint de verificación del webhook de Meta.

    Meta enviará:
      GET ?hub.mode=subscribe&hub.challenge=NONCE&hub.verify_token=TU_TOKEN

    Si el token coincide, respondemos con el challenge (plain text).
    """
    settings = request.app.state.settings
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("WhatsApp webhook verificado correctamente.")
        return hub_challenge
    logger.warning(
        "Intento de verificación fallido. mode=%s token_match=%s",
        hub_mode, hub_verify_token == settings.whatsapp_verify_token,
    )
    raise HTTPException(status_code=403, detail="Verify token inválido.")


# ── POST: mensajes entrantes ──────────────────────────────────────────────────

@router.post("/whatsapp", status_code=200)
async def whatsapp_webhook(
    request: Request,
    payload: WhatsAppWebhookPayload,
    background_tasks: BackgroundTasks,
) -> dict:
    """Recibe mensajes de WhatsApp. Responde 200 inmediatamente y procesa en background."""
    # Extraer el primer mensaje válido del payload
    message_info = _extract_message(payload)
    if message_info is None:
        # Payload sin mensajes (ej: status updates de entrega) → ignorar
        return {"status": "ignored"}

    phone, name, message_id, text = message_info

    # Anti-duplicados: mensaje ya procesado
    processed_ids: set[str] = request.app.state.processed_message_ids
    if message_id in processed_ids:
        logger.debug("Mensaje duplicado ignorado: %s", message_id)
        return {"status": "duplicate"}
    processed_ids.add(message_id)
    # Evitar que el set crezca indefinidamente
    if len(processed_ids) > 10_000:
        processed_ids.clear()

    # Marcar como leído (fire-and-forget, no bloquea)
    background_tasks.add_task(
        _mark_read_and_process,
        request=request,
        phone=phone,
        name=name,
        message_id=message_id,
        text=text,
    )

    return {"status": "accepted"}


def _extract_message(
    payload: WhatsAppWebhookPayload,
) -> tuple[str, str, str, str] | None:
    """Extrae (phone, name, message_id, text) del primer mensaje de texto del payload.

    Retorna None si no hay mensajes de texto (ej: status updates).
    """
    for entry in payload.entry:
        for change in entry.changes:
            value = change.value
            if not value.messages:
                continue
            for msg in value.messages:
                if msg.type == "text" and msg.text:
                    phone = msg.from_
                    name = (
                        value.contacts[0].profile.name
                        if value.contacts
                        else phone
                    )
                    return phone, name, msg.id, msg.text.body
    return None


async def _mark_read_and_process(
    *,
    request: Request,
    phone: str,
    name: str,
    message_id: str,
    text: str,
) -> None:
    """BackgroundTask: marca como leído + invoca el grafo + envía respuesta."""
    messaging_service = request.app.state.messaging_service
    whatsapp_graph = request.app.state.whatsapp_graph
    scheduling_service = request.app.state.scheduling_service
    lead_service = request.app.state.lead_service

    # Marcar como leído para mejor UX (doble tick azul)
    await messaging_service.mark_as_read(message_id)

    thread_id = f"wa_{phone}"
    logger.info("Procesando mensaje de %s (thread=%s): %s", phone, thread_id, text[:60])

    initial_state: dict = {
        "messages": [{"role": "user", "content": text}],
        "sender_phone": phone,
        "sender_name": name,
        "intent": "",
        "lead_quality": "unknown",
        "lead_email": "",
        "lead_project_type": "",
        "lead_budget_hint": "",
        "lead_service_type": "",
        "response_text": "",
    }

    try:
        result = await whatsapp_graph.ainvoke(
            initial_state,
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "scheduling_service": scheduling_service,
                    "lead_service": lead_service,
                }
            },
        )
        response_text = result.get("response_text", "")
        if not response_text:
            # Fallback si el agente no generó response_text
            messages = result.get("messages", [])
            if messages:
                raw = messages[-1].content
                response_text = raw if isinstance(raw, str) else " ".join(
                    b.get("text", "") if isinstance(b, dict) else str(b) for b in raw
                ) if isinstance(raw, list) else str(raw)

        if response_text:
            await messaging_service.send_text(phone, response_text)
            logger.info("Respuesta enviada a %s (%d chars)", phone, len(response_text))
        else:
            logger.warning("No se generó respuesta para %s", phone)

    except Exception as e:
        logger.exception("Error procesando mensaje de %s: %s", phone, e)
        # En producción podríamos enviar un mensaje de error genérico al usuario
        await messaging_service.send_text(
            phone,
            "Lo siento, ocurrió un error procesando tu mensaje. "
            "Por favor intenta nuevamente o escríbenos a hola@girosmedia.cl",
        )
