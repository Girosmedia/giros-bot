"""Implementación concreta de IMessagingService usando Meta Graph API.

En modo desarrollo (whatsapp_phone_number_id vacío) loguea el mensaje
en lugar de llamar a Meta, para poder desarrollar sin credenciales reales.
"""

import logging

import httpx

from ..config import Settings
from ..services.messaging import IMessagingService

logger = logging.getLogger(__name__)


class WhatsAppAPIMessaging:
    """Implementa IMessagingService usando Meta Cloud API (WhatsApp Business)."""

    def __init__(self, settings: Settings) -> None:
        self._phone_number_id = settings.whatsapp_phone_number_id
        self._api_token = settings.whatsapp_api_token
        self._api_version = settings.whatsapp_api_version
        self._dev_mode = not bool(self._phone_number_id and self._api_token)

        if self._dev_mode:
            logger.warning(
                "WhatsAppAPIMessaging iniciado en DEV MODE — "
                "los mensajes se loguean, no se envían a Meta."
            )

    @property
    def _base_url(self) -> str:
        return (
            f"https://graph.facebook.com/{self._api_version}"
            f"/{self._phone_number_id}/messages"
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

    async def send_text(self, recipient_id: str, text: str) -> bool:
        if self._dev_mode:
            logger.info("[DEV] WhatsApp → %s: %s", recipient_id, text[:120])
            return True

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_id,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._base_url, headers=self._headers, json=payload)
                resp.raise_for_status()
                logger.info("Mensaje enviado a %s (status=%d)", recipient_id, resp.status_code)
                return True
        except httpx.HTTPStatusError as e:
            logger.error(
                "Error Meta API al enviar mensaje a %s: %s — %s",
                recipient_id, e.response.status_code, e.response.text,
            )
            return False
        except Exception as e:
            logger.error("Error inesperado enviando mensaje a %s: %s", recipient_id, e)
            return False

    async def mark_as_read(self, message_id: str) -> bool:
        if self._dev_mode:
            logger.debug("[DEV] mark_as_read → %s", message_id)
            return True

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(self._base_url, headers=self._headers, json=payload)
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.warning("No se pudo marcar como leído %s: %s", message_id, e)
            return False


# Verificación estática de que la clase implementa el Protocol
_: IMessagingService = WhatsAppAPIMessaging.__new__(WhatsAppAPIMessaging)  # type: ignore[assignment]
