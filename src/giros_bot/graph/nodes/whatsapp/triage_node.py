"""triage_node — clasifica el intent del mensaje entrante.

Sin tools. Responde con JSON {intent, quick_ack} y enruta con Command(goto=intent).
Es el primer nodo que se ejecuta en cada turno de conversación.
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.types import Command

from ....config import settings
from ....prompts.whatsapp import TRIAGE_PROMPT
from ....schemas.whatsapp_state import TriageIntent, WhatsAppState

logger = logging.getLogger(__name__)

_llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=settings.google_api_key,
    temperature=0.1,  # Baja temperatura para clasificación consistente
)

_FALLBACK_INTENT = TriageIntent.INFO_GENERAL


async def triage_node(state: WhatsAppState, config: RunnableConfig) -> Command:
    """Clasifica el último mensaje del usuario y enruta al agente correspondiente."""
    messages = state.get("messages", [])
    if not messages:
        logger.warning("triage_node recibió state sin mensajes.")
        return Command(goto=_FALLBACK_INTENT.value, update={"intent": _FALLBACK_INTENT.value})

    # Tomar solo el último mensaje del usuario para clasificar
    last_message = messages[-1]
    user_text = last_message.content if hasattr(last_message, "content") else str(last_message)

    try:
        response = await _llm.ainvoke(
            [
                SystemMessage(content=TRIAGE_PROMPT),
                HumanMessage(content=user_text),
            ]
        )
        raw = str(response.content).strip()
        # Limpiar posible markdown que el LLM añada
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        intent_str = data.get("intent", _FALLBACK_INTENT.value)
        quick_ack = data.get("quick_ack", "")

        # Validar que el intent existe
        try:
            intent = TriageIntent(intent_str)
        except ValueError:
            logger.warning("Intent desconocido '%s', usando fallback.", intent_str)
            intent = _FALLBACK_INTENT

        logger.info(
            "triage_node → intent=%s phone=%s",
            intent.value, state.get("sender_phone", "?"),
        )

        return Command(
            goto=intent.value,
            update={
                "intent": intent.value,
                # Si triage generó un quick_ack, lo ponemos como respuesta temporal
                # (los agentes lo sobreescribirán con su respuesta completa)
                "response_text": quick_ack,
            },
        )

    except (json.JSONDecodeError, Exception) as e:
        logger.error("Error en triage_node: %s — usando fallback.", e)
        return Command(
            goto=_FALLBACK_INTENT.value,
            update={"intent": _FALLBACK_INTENT.value},
        )
