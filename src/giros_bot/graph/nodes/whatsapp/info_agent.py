"""info_agent — consultor de marketing digital general.

Sin tools. Responde preguntas generales con CTA suave al final.
"""

import logging

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

from ....config import settings
from ....prompts.whatsapp import INFO_GENERAL_PROMPT
from ....schemas.whatsapp_state import WhatsAppState

logger = logging.getLogger(__name__)

_llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=settings.google_api_key,
    temperature=0.7,
)


def _content_str(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


async def info_agent(state: WhatsAppState, config: RunnableConfig) -> dict:
    """Agente informativo: responde consultas generales de marketing digital."""
    msgs = [SystemMessage(content=INFO_GENERAL_PROMPT)] + list(state["messages"])
    response = await _llm.ainvoke(msgs, config=config)
    response_text = _content_str(response.content)
    logger.info("info_agent respondió a %s", state.get("sender_phone", "?"))
    return {"messages": [response], "response_text": response_text}
