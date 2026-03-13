"""Tool: get_scheduling_link — bridge Agente → ISchedulingService.

El agente llama este tool cuando decide que el lead califica.
El tool obtiene el servicio de agenda desde RunnableConfig["configurable"],
completamente agnóstico del proveedor real.
"""

import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from ..services.scheduling import ISchedulingService

logger = logging.getLogger(__name__)


@tool
async def get_scheduling_link(
    lead_name: str,
    project_type: str,
    config: RunnableConfig,
) -> str:
    """Obtiene el link o instrucción de agenda según el proveedor configurado.

    Usar este tool cuando el lead ha calificado (lead_quality=HIGH) y quiere agendar
    una reunión con el equipo de Giros Media.

    Args:
        lead_name: Nombre del lead (para pre-fill si el proveedor lo soporta).
        project_type: Tipo de proyecto o consulta del lead.
        config: Inyectado automáticamente por LangGraph.

    Returns:
        Texto con la instrucción + URL de agenda para incluir en la respuesta.
    """
    configurable = config.get("configurable") or {}
    scheduling_service: ISchedulingService = configurable["scheduling_service"]
    context = {
        "lead_name": lead_name,
        "project_type": project_type,
    }
    try:
        result = await scheduling_service.get_booking_url(context)
        if result.available:
            return f"{result.instructions} {result.booking_url}".strip()
        return result.instructions
    except Exception as e:
        logger.error("Error obteniendo link de agenda: %s", e)
        return (
            "En este momento no podemos generar el link de agenda. "
            "Escríbenos a hola@girosmedia.cl y coordinamos directamente."
        )
