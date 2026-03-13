"""reserva_agent — filtro VIP para reuniones con el equipo directivo.

Hace 2-3 preguntas de calificación ANTES de revelar la URL de agenda.
Tools: get_scheduling_link, capture_lead.
"""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import ToolNode

from ....config import settings
from ....prompts.whatsapp import AGENDAR_PROMPT
from ....schemas.whatsapp_state import WhatsAppState
from ....tools.lead_tool import capture_lead
from ....tools.scheduling_tool import get_scheduling_link

logger = logging.getLogger(__name__)

_tools = [get_scheduling_link, capture_lead]
_tool_node = ToolNode(_tools)
_llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=settings.google_api_key,
    temperature=0.6,
)
_llm_with_tools = _llm.bind_tools(_tools)


def _content_str(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


async def reserva_agent(state: WhatsAppState, config: RunnableConfig) -> dict:
    """Califica el lead con 2-3 preguntas antes de revelar la agenda (VIP filter)."""
    msgs = [SystemMessage(content=AGENDAR_PROMPT)] + list(state["messages"])

    response: AIMessage = await _llm_with_tools.ainvoke(msgs, config=config)

    if response.tool_calls:
        tool_result = await _tool_node.ainvoke({"messages": [response]}, config=config)
        msgs = msgs + [response] + tool_result["messages"]
        response = await _llm_with_tools.ainvoke(msgs, config=config)

    response_text = _content_str(response.content)
    logger.info("reserva_agent respondió a %s", state.get("sender_phone", "?"))
    return {"messages": [response], "response_text": response_text}
