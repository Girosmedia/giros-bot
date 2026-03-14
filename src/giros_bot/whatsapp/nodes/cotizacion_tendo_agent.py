"""cotizacion_tendo_agent — cierra trials de Tendo SaaS.

Precios abiertos: $20.000 CLP/mes.
Tool disponible: capture_lead.
"""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import ToolNode

from ...config import settings
from ..prompts import COTIZACION_TENDO_PROMPT
from ..state import WhatsAppState
from ..tools.lead_tool import capture_lead

logger = logging.getLogger(__name__)

_tools = [capture_lead]
_tool_node = ToolNode(_tools)
_llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=settings.google_api_key,
    temperature=0.7,
)
_llm_with_tools = _llm.bind_tools(_tools)


def _content_str(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


async def cotizacion_tendo_agent(state: WhatsAppState, config: RunnableConfig) -> dict:
    """Agente especializado en Tendo SaaS. Precios abiertos, objetivo: trial 14 días."""
    msgs = [SystemMessage(content=COTIZACION_TENDO_PROMPT)] + list(state["messages"])

    response: AIMessage = await _llm_with_tools.ainvoke(msgs, config=config)

    if response.tool_calls:
        tool_result = await _tool_node.ainvoke({"messages": [response]}, config=config)
        msgs = msgs + [response] + tool_result["messages"]
        response = await _llm_with_tools.ainvoke(msgs, config=config)

    response_text = _content_str(response.content)
    logger.info(
        "cotizacion_tendo_agent respondió a %s", state.get("sender_phone", "?")
    )
    return {"messages": [response], "response_text": response_text}
