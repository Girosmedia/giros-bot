"""Tool: capture_lead — bridge Agente → ILeadCaptureService.

Persiste el lead en el sistema configurado (PostgreSQL en prod, mock en tests).
Todos los args son opcionales excepto phone + name para no bloquear al agente
si aún no recopiló todos los datos.
"""

import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from ..services.lead_capture import ILeadCaptureService, LeadData

logger = logging.getLogger(__name__)


@tool
async def capture_lead(
    phone: str,
    name: str,
    config: RunnableConfig,
    email: str = "",
    project_type: str = "",
    budget_hint: str = "",
    service_type: str = "",
    lead_quality: str = "unknown",
    notes: str = "",
) -> str:
    """Persiste el lead capturado en el sistema de CRM/DB configurado.

    Llamar este tool cuando:
    - Se obtuvo el email del usuario (cotizacion_servicios)
    - Se cerró un trial de Tendo (cotizacion_tendo)
    - El lead calificó o no para agenda (reserva_agent)

    Args:
        phone: Número de teléfono del lead (obligatorio).
        name: Nombre del lead (obligatorio).
        email: Email de contacto.
        project_type: Tipo de proyecto o servicio de interés.
        budget_hint: "tiene_budget" | "explorando" | "sin_budget" | "".
        service_type: "servicios" | "tendo" | "agenda".
        lead_quality: "unknown" | "high" | "low".
        notes: Notas adicionales de la conversación.
        config: Inyectado automáticamente por LangGraph.

    Returns:
        Confirmación de guardado o mensaje de error.
    """
    configurable = config.get("configurable") or {}
    lead_service: ILeadCaptureService = configurable["lead_service"]
    lead = LeadData(
        phone=phone,
        name=name,
        email=email,
        project_type=project_type,
        budget_hint=budget_hint,
        service_type=service_type,
        lead_quality=lead_quality,
        notes=notes,
    )
    try:
        saved = await lead_service.save_lead(lead)
        if saved:
            logger.info("Lead capturado: %s <%s> tipo=%s", name, phone, service_type)
            return "Lead guardado correctamente."
        return "No se pudo guardar el lead (error interno)."
    except Exception as e:
        logger.error("Error capturando lead %s: %s", phone, e)
        return "Error al guardar el lead."
