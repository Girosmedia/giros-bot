"""triage_node — clasifica el intent del mensaje entrante.

Sin tools. Responde con JSON {intent, quick_ack} y enruta con Command(goto=intent).
Es el primer nodo que se ejecuta en cada turno de conversación.
"""

import ast
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.types import Command

from ...config import settings
from ..prompts import TRIAGE_PROMPT
from ..state import TriageIntent, WhatsAppState

logger = logging.getLogger(__name__)

_llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=settings.google_api_key,
    temperature=0.1,  # Baja temperatura para clasificación consistente
)

_FALLBACK_INTENT = TriageIntent.INFO_GENERAL


def _parse_llm_json(raw: str) -> dict:
    """Parsea JSON de la respuesta del LLM con múltiples estrategias de fallback.

    El LLM a veces devuelve:
    - Bloques markdown ```json ... ```
    - Dicts Python con comillas simples {'intent': '...'}
    - JSON válido directo
    """
    raw = raw.strip()

    # Extraer contenido de bloque markdown ```...```
    if "```" in raw:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            raw = match.group(1).strip()

    # Estrategia 1: JSON estándar
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Estrategia 2: ast.literal_eval (maneja dicts Python con comillas simples)
    try:
        result = ast.literal_eval(raw)
        if isinstance(result, dict):
            return result
    except (ValueError, SyntaxError):
        pass

    # Estrategia 3: extraer el primer objeto JSON con regex
    match = re.search(r"\{[\s\S]*?\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No se pudo parsear JSON de: {raw[:120]}")


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
        data = _parse_llm_json(raw)
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
