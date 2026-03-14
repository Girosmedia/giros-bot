"""Capa 4 — Abstracción de agendamiento.

Define el contrato (Protocol) y el resultado genérico (SchedulingResult).
Los agentes solo ven SchedulingResult, nunca el proveedor concreto.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class SchedulingResult:
    """Resultado genérico de una consulta de disponibilidad.

    El agente usa este objeto para componer la respuesta al usuario.
    El proveedor real (Calendly, Google Cal, manual…) es completamente opaco.
    """

    available: bool
    booking_url: str      # URL directa o instrucción textual si no hay URL
    provider_name: str    # "Calendly" | "Google Calendar" | "Manual"
    instructions: str     # Texto amigable para el usuario final


@runtime_checkable
class ISchedulingService(Protocol):
    """Contrato para obtener disponibilidad y links de agenda."""

    async def get_booking_url(self, context: dict) -> SchedulingResult:
        """Retorna un SchedulingResult con la URL/instrucción de agenda.

        Args:
            context: dict opcional con claves como:
                - lead_name (str)
                - lead_phone (str)
                - project_type (str)
                Usado por implementaciones que soportan pre-fill (Calendly API v2, Google Cal).

        Returns:
            SchedulingResult con available=True si hay slots, False si no.
        """
        ...
