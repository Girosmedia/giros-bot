"""Capa 4 — Abstracción de captura de leads.

Define el contrato (Protocol) y el modelo de datos (LeadData).
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class LeadData:
    """Datos de un lead capturado durante una conversación de WhatsApp."""

    phone: str
    name: str
    email: str = ""
    project_type: str = ""   # "web_landing"|"web_ecommerce"|"web_app"|"automatizacion"|
                              # "rrss"|"identidad_marca"|"diseno"|"tendo"|"otro"
    budget_hint: str = ""    # "tiene_budget"|"explorando"|"sin_budget"|""
    service_type: str = ""   # "servicios"|"tendo"|"agenda"
    lead_quality: str = "unknown"   # "unknown"|"high"|"low"
    notes: str = ""
    tags: list[str] = field(default_factory=list)


@runtime_checkable
class ILeadCaptureService(Protocol):
    """Contrato para persistir o notificar leads capturados."""

    async def save_lead(self, lead: LeadData) -> bool:
        """Persiste o notifica el lead al sistema configurado.

        Args:
            lead: Datos del lead recopilados durante la conversación.

        Returns:
            True si el lead fue grabado/notificado correctamente.
        """
        ...
