"""STUB — GoogleCalendarScheduler.

Implementar cuando se defina la integración con Google Calendar / Google Workspace.
Para activar: cambiar en main.py el lifespan de
    CalendlyScheduler → GoogleCalendarScheduler
"""

from .base import SchedulingResult


class GoogleCalendarScheduler:
    """STUB — implementar cuando se defina el proveedor de Google Calendar."""

    async def get_booking_url(self, context: dict) -> SchedulingResult:
        raise NotImplementedError(
            "GoogleCalendarScheduler no está implementado aún. "
            "Configura scheduling_provider=calendly en .env o implementa esta clase."
        )
