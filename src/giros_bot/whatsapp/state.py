"""Estado del grafo LangGraph para el agente de WhatsApp.

Usa TypedDict + Annotated con add_messages reducer para acumulación
de historial (patrón estándar LangGraph).
"""

from enum import StrEnum
from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class TriageIntent(StrEnum):
    COTIZACION_TENDO = "cotizacion_tendo"
    COTIZACION_SERVICIOS = "cotizacion_servicios"
    SOPORTE = "soporte_tecnico"
    INFO_GENERAL = "info_general"
    AGENDAR = "agendar_llamada"
    OUT_OF_SCOPE = "out_of_scope"


class LeadQuality(StrEnum):
    UNKNOWN = "unknown"
    HIGH = "high"   # → revela URL de agenda
    LOW = "low"     # → desvía a web/PDF


class WhatsAppState(TypedDict):
    # Historial de mensajes LangChain (acumulativo por thread_id)
    messages: Annotated[list, add_messages]

    # Datos del remitente (poblar desde el payload webhook)
    sender_phone: str
    sender_name: str

    # Resultado del triage
    intent: str   # valor de TriageIntent

    # Datos de calificación del lead (se van llenando durante la conversación)
    lead_quality: str      # valor de LeadQuality
    lead_email: str
    lead_project_type: str  # "web_ecommerce"|"web_landing"|"web_app"|"automatizacion"|
                             # "rrss"|"identidad_marca"|"diseno"|"tendo"|""
    lead_budget_hint: str   # "tiene_budget"|"explorando"|"sin_budget"|""
    lead_service_type: str  # "servicios"|"tendo"|"agenda"

    # Respuesta final que el route handler enviará por WhatsApp
    response_text: str
