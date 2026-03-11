"""
Scout_Agent — Investigador dinámico con acceso a herramientas de búsqueda web.
Ahora el LLM decide sus propias queries basándose en la categoría asignada.
"""

import logging
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from giros_bot.config import settings
from giros_bot.prompts.scout import SCOUT_PROMPT_TEMPLATE
from giros_bot.prompts.system import SYSTEM_IDENTITY
from giros_bot.schemas.state import AgentState
from giros_bot.tools.tavily_tool import search_web

logger = logging.getLogger(__name__)

async def scout_node(state: AgentState) -> dict:
    """Nodo del Scout: Investiga usando herramientas y sintetiza la información."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview", # Motor de búsqueda e investigación de última generación
        temperature=0.5,
        google_api_key=settings.google_api_key,
    ).bind_tools([search_web])

    target_cat = state.target_category.value if state.target_category else "Marketing Digital"
    
    # ── 1. Preparar Mensajes ──────────────────────────────────────────────────
    prompt = SCOUT_PROMPT_TEMPLATE.format(
        target_date=state.target_date,
        target_category=target_cat,
        recent_history_context=state.recent_history_context,
    )

    messages = [
        SystemMessage(content=SYSTEM_IDENTITY),
        HumanMessage(content=prompt),
    ]

    # ── 2. Loop de Ejecución (LLM + Tools) ────────────────────────────────────
    # Permitimos hasta 2 iteraciones de búsqueda si el LLM lo requiere
    for i in range(2):
        response = await llm.ainvoke(messages)
        messages.append(response)

        # Si no hay tool_calls, terminamos el loop
        if not response.tool_calls:
            break

        # Ejecutar las herramientas solicitadas
        for tool_call in response.tool_calls:
            if tool_call["name"] == "search_web":
                tool_result = await search_web.ainvoke(tool_call["args"])
                messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call["id"]
                ))
            else:
                logger.warning("Scout: Tool desconocida solicitada: %s", tool_call["name"])

    # ── 3. Sintetizar Resultado Final ─────────────────────────────────────────
    # Si la última respuesta aún tiene tool_calls pero agotamos el loop,
    # forzamos una última llamada sin herramientas para obtener el JSON.
    final_response = response
    if response.tool_calls:
        final_response = await llm.ainvoke(messages + [HumanMessage(content="Genera ahora el JSON final con tu investigación.")])

    # Limpiar y parsear JSON
    _content = final_response.content
    raw = (
        "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in _content
        ).strip()
        if isinstance(_content, list)
        else _content.strip()
    )
    
    # Limpieza estándar de bloques de código
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].strip()

    try:
        data = json.loads(raw)
        internal_knowledge = data.get("internal_knowledge", "")
        market_context = data.get("market_context", "")
    except json.JSONDecodeError:
        logger.warning("Scout: No se pudo parsear JSON final, usando raw")
        internal_knowledge = raw
        market_context = "Error en el parseo del contexto de mercado."

    logger.info(
        "Scout completado dinámicamente. Categoría: %s | Herramientas usadas.",
        target_cat
    )

    return {
        "internal_knowledge": internal_knowledge,
        "market_context": market_context,
    }
