"""Tool: send_whatsapp_message — usado exclusivamente en tests.

En producción, el route handler llama messaging_service.send_text() directamente
(no a través del agente) para mantener la respuesta < 200ms.
Este tool existe para poder testear el flujo de envío en tests unitarios.
"""

import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from ..whatsapp.services.messaging import IMessagingService

logger = logging.getLogger(__name__)


@tool
async def send_whatsapp_message(
    recipient_phone: str,
    text: str,
    config: RunnableConfig,
) -> str:
    """Envía un mensaje de texto por WhatsApp al destinatario indicado.

    NOTA: En producción este tool no es usado por los agentes.
    El route handler envía la respuesta directamente tras recibir response_text del grafo.

    Args:
        recipient_phone: Número E.164 del destinatario (ej: 56912345678).
        text: Texto a enviar.
        config: Inyectado automáticamente por LangGraph.
    """
    messaging_service: IMessagingService = config["configurable"]["messaging_service"]
    sent = await messaging_service.send_text(recipient_phone, text)
    return "Mensaje enviado." if sent else "Error al enviar el mensaje."
