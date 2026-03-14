"""Compilación del StateGraph para el agente de WhatsApp.

Arquitectura:
    triage_node → [cotizacion_tendo_agent | cotizacion_servicios_agent |
                    soporte_agent | info_agent | reserva_agent | out_of_scope_node]

Los servicios (scheduling, lead) se inyectan en la invocación del grafo
vía config["configurable"], nunca import en los nodos.
"""

import logging
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .state import TriageIntent, WhatsAppState
from .services.lead_capture import ILeadCaptureService
from .services.scheduling import ISchedulingService
from .nodes.cotizacion_servicios_agent import cotizacion_servicios_agent
from .nodes.cotizacion_tendo_agent import cotizacion_tendo_agent
from .nodes.info_agent import info_agent
from .nodes.reserva_agent import reserva_agent
from .nodes.soporte_agent import soporte_agent
from .nodes.triage_node import triage_node

logger = logging.getLogger(__name__)


async def out_of_scope_node(state: WhatsAppState, config) -> dict:
    """Respuesta para mensajes fuera del scope del bot."""
    return {
        "response_text": (
            "Hola 👋 Soy el asistente de Giros Media. "
            "Puedo ayudarte con información sobre nuestros servicios digitales, "
            "cotizaciones o soporte. ¿En qué te puedo orientar?"
        )
    }


def build_whatsapp_graph(
    checkpointer: Any,
    scheduling_service: ISchedulingService,
    lead_service: ILeadCaptureService,
) -> CompiledStateGraph:
    """Construye y compila el StateGraph del agente WhatsApp.

    Args:
        checkpointer: AsyncPostgresSaver (o MemorySaver) para persistir el historial.
        scheduling_service: Implementación de ISchedulingService (CalendlyScheduler, etc.)
        lead_service: Implementación de ILeadCaptureService (PostgresLeadCapture, etc.)

    Returns:
        Grafo compilado listo para ainvoke().

    Los servicios NO se almacenan en el grafo. Se pasan en cada invocación:
        await graph.ainvoke(
            input,
            config={
                "configurable": {
                    "thread_id": "wa_56912345678",
                    "scheduling_service": scheduling_service,
                    "lead_service": lead_service,
                }
            }
        )
    """
    builder = StateGraph(WhatsAppState)

    # Nodos
    builder.add_node("triage_node", triage_node)
    builder.add_node(TriageIntent.COTIZACION_TENDO.value, cotizacion_tendo_agent)
    builder.add_node(TriageIntent.COTIZACION_SERVICIOS.value, cotizacion_servicios_agent)
    builder.add_node(TriageIntent.SOPORTE.value, soporte_agent)
    builder.add_node(TriageIntent.INFO_GENERAL.value, info_agent)
    builder.add_node(TriageIntent.AGENDAR.value, reserva_agent)
    builder.add_node(TriageIntent.OUT_OF_SCOPE.value, out_of_scope_node)

    # Entry point
    builder.set_entry_point("triage_node")

    # Edges: cada agente finaliza en END (el grafo se re-invoca en el siguiente mensaje)
    for intent in TriageIntent:
        builder.add_edge(intent.value, END)

    # triage_node usa Command(goto=...) — el routing dinámico lo maneja LangGraph
    # No es necesario add_conditional_edges cuando el nodo retorna Command

    graph = builder.compile(checkpointer=checkpointer)
    logger.info("WhatsApp graph compilado con %d nodos.", len(list(TriageIntent)) + 1)
    return graph
