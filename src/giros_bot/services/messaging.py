"""Capa 4 — Abstracción de mensajería.

Define solo el contrato (Protocol). Ningún agente ni tool importa
implementaciones concretas desde aquí.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class IMessagingService(Protocol):
    """Contrato para enviar mensajes a usuarios finales."""

    async def send_text(self, recipient_id: str, text: str) -> bool:
        """Envía un mensaje de texto plano.

        Args:
            recipient_id: Identificador del destinatario (ej: número E.164 en WhatsApp).
            text: Contenido del mensaje.

        Returns:
            True si el envío fue aceptado por el proveedor.
        """
        ...

    async def mark_as_read(self, message_id: str) -> bool:
        """Marca un mensaje recibido como leído (mejora UX).

        Args:
            message_id: ID del mensaje a marcar.

        Returns:
            True si la operación fue exitosa.
        """
        ...
