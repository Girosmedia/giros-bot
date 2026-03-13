"""Implementación CalendlyScheduler — Fase 1 (URL estática).

V1: retorna la URL de Calendly configurada sin pre-fill.
V2 futura: usar Calendly API v2 para crear single-use links con datos del lead.
"""

import logging

from .base import SchedulingResult

logger = logging.getLogger(__name__)


class CalendlyScheduler:
    """Implementa ISchedulingService usando una URL de Calendly estática.

    Swap por GoogleCalendarScheduler = cambiar 1 línea en el lifespan de FastAPI.
    """

    def __init__(self, calendly_url: str) -> None:
        self._url = calendly_url
        if not calendly_url:
            logger.warning(
                "CalendlyScheduler iniciado sin URL configurada. "
                "Establece SCHEDULING_URL en .env."
            )

    async def get_booking_url(self, context: dict) -> SchedulingResult:
        """Retorna la URL de Calendly. Context ignorado en V1 (sin pre-fill)."""
        if not self._url:
            return SchedulingResult(
                available=False,
                booking_url="",
                provider_name="Calendly",
                instructions=(
                    "En este momento no tenemos agenda online disponible. "
                    "Te contactaremos directamente para coordinar una reunión."
                ),
            )

        return SchedulingResult(
            available=True,
            booking_url=self._url,
            provider_name="Calendly",
            instructions="Puedes agendar tu reunión directamente aquí →",
        )
