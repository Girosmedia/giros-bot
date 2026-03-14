"""
Compilación del StateGraph de LangGraph.

Flujo principal:
  scheduler → scout → strategist → writer → social → visual → validator
                                              ↑ (retry si quality_score < 7, max 2x)
                                              └─────────────────────────────┘
  validator (approved) → publisher → END
"""

import logging
from typing import Literal

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from ..schemas.state import AgentState
from .nodes.publisher import publisher_node
from .nodes.scheduler import scheduler_node
from .nodes.scout import scout_node
from .nodes.social import social_node
from .nodes.strategist import strategist_node
from .nodes.validator import validator_node
from .nodes.visual import visual_node
from .nodes.writer import writer_node
from .state import AgentStateDict

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


def should_retry_or_publish(state: AgentStateDict) -> Literal["writer", "publisher"]:
    """
    Router condicional post-validación.
    retry_count se incrementa en el validator con cada pasada.
    Si quality_score < 9 y retry_count <= MAX_RETRIES → vuelve al writer.
    De lo contrario → publisher (con el MDX que tenga, aunque sea imperfecto).
    """
    score = state.get("quality_score", 0)
    retries = state.get("retry_count", 0)

    if score < 9 and retries <= MAX_RETRIES:
        logger.info(
            "Validator: score=%d < 9. Retry #%d/%d → writer",
            score, retries, MAX_RETRIES,
        )
        return "writer"

    logger.info(
        "Validator: score=%d. retry_count=%d → publisher",
        score, retries,
    )
    return "publisher"


# ── Wrapper para incrementar retry_count antes de re-entrar al writer ────────
async def writer_with_retry(state: AgentStateDict) -> dict:
    """Incrementa el contador de retries y llama al writer_node."""
    from .nodes.writer import writer_node as _writer

    retry_count = state.get("retry_count", 0) + 1
    result = await _writer(AgentState(**state))
    return {**result, "retry_count": retry_count}


# ── Wrappers para adaptar AgentStateDict ↔ AgentState ────────────────────────
def _wrap(node_fn):
    """Adapta un nodo que recibe AgentState a uno que recibe AgentStateDict."""
    async def wrapper(state: AgentStateDict) -> dict:
        normalized_state = {
            k: (v.model_dump() if isinstance(v, BaseModel) else v)
            for k, v in state.items()
            if v is not None
        }
        agent_state = AgentState(**normalized_state)
        return await node_fn(agent_state)
    wrapper.__name__ = node_fn.__name__
    return wrapper


def build_graph() -> StateGraph:
    """Construye y compila el StateGraph de giros-bot."""
    graph = StateGraph(AgentStateDict)

    # Agregar nodos
    graph.add_node("scheduler",  _wrap(scheduler_node))
    graph.add_node("scout",      _wrap(scout_node))
    graph.add_node("strategist", _wrap(strategist_node))
    graph.add_node("writer",     _wrap(writer_node))
    graph.add_node("social",     _wrap(social_node))
    graph.add_node("visual",     _wrap(visual_node))
    graph.add_node("validator",  _wrap(validator_node))
    graph.add_node("publisher",  _wrap(publisher_node))

    # Flujo lineal principal
    graph.set_entry_point("scheduler")
    graph.add_edge("scheduler",  "scout")
    graph.add_edge("scout",      "strategist")
    graph.add_edge("strategist", "writer")
    graph.add_edge("writer",     "social")
    graph.add_edge("social",     "visual")
    graph.add_edge("visual",     "validator")

    # Router condicional post-validación
    graph.add_conditional_edges(
        "validator",
        should_retry_or_publish,
        {
            "writer":    "writer",      # Retry loop
            "publisher": "publisher",   # Publicar
        },
    )

    graph.add_edge("publisher", END)

    return graph.compile()


async def run_pipeline(target_date: str) -> AgentStateDict:
    """
    Ejecuta el pipeline completo para una fecha dada.

    Args:
        target_date: Fecha en formato YYYY-MM-DD.

    Returns:
        Estado final del grafo con todos los assets generados.
    """
    compiled = build_graph()

    initial_state: AgentStateDict = {
        "target_date":    target_date,
        "content_type":   None,
        "recent_history_context": "",
        "recent_visual_context":  "",
        "market_context": "",
        "internal_knowledge": "",
        "title":          "",
        "slug":           "",
        "frontend_category": None,
        "tags":           [],
        "description":    "",
        "mdx_content_body": "",
        "social_brief":   "",
        "visual_brief":   "",
        "social_assets":  None,
        "image_prompt":   "",
        "image_alt":      "",
        "image_url_generated": "",
        "image_bytes_b64": "",
        "article_format": None,
        "editorial_brief": "",
        "hero_product":   "",
        "selling_intensity": "soft",
        "quality_score":  0,
        "retry_count":    0,
        "error_message":  "",
    }

    final_state = await compiled.ainvoke(initial_state)
    logger.info("Pipeline completado para %s. quality_score=%d", target_date, final_state.get("quality_score", 0))
    return final_state
