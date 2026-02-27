"""
Scout_Agent — RAG simplificado sobre knowledge_base/ + búsqueda web Tavily.

Flujo:
  1. Carga SIEMPRE ambos archivos del cerebro de la agencia:
       00_CEREBRO_OFERTA_GLOBAL.md  (Precios, specs, Tendo, packs — Hemisferio Izq.)
       00_CEREBRO_IDENTIDAD.md      (Tono, misión, filosofía — Hemisferio Der.)
     Cargar ambos permite cruces: ej. hacer un soft sell dentro de un post Consejo.
  2. Intenta Tavily Search para obtener contexto de mercado fresco (2 queries).
  3. Si Tavily falla → fallback: el LLM genera market_context desde su entrenamiento.
  4. El LLM sintetiza ambas fuentes en internal_knowledge + market_context.
"""

import logging
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ...config import settings
from ...prompts.scout import SCOUT_PROMPT_TEMPLATE
from ...prompts.system import SYSTEM_IDENTITY
from ...schemas.state import AgentState
from ...tools.tavily_tool import search_market_context

logger = logging.getLogger(__name__)

# Ruta a la knowledge base — parents[4] = raíz del proyecto giros-bot/
KNOWLEDGE_BASE_DIR = Path(__file__).parents[4] / "knowledge_base"


# Cerebro completo — siempre se carga, sin filtrar por content_type
CORE_KNOWLEDGE_FILES = [
    "00_CEREBRO_OFERTA_GLOBAL.md",  # Datos duros: precios, specs, Tendo, packs
    "00_CEREBRO_IDENTIDAD.md",      # Datos blandos: tono, misión, filosofía
]


def _load_full_context() -> str:
    """Carga el cerebro completo de la agencia (Hemisferio Izq + Der).

    Returns:
        Texto concatenado de ambos archivos, o string vacío si no existen.
    """
    if not KNOWLEDGE_BASE_DIR.exists():
        logger.warning("knowledge_base/ no encontrado en %s", KNOWLEDGE_BASE_DIR)
        return ""

    docs = []
    for filename in CORE_KNOWLEDGE_FILES:
        file_path = KNOWLEDGE_BASE_DIR / filename
        if file_path.exists():
            docs.append(f"=== FUENTE: {filename} ===\n\n{file_path.read_text(encoding='utf-8')}")
        else:
            logger.warning("Archivo crítico no encontrado: %s", file_path)

    return "\n\n---\n\n".join(docs)


async def scout_node(state: AgentState) -> dict:
    """Carga KB, busca contexto web con Tavily (fallback LLM) y sintetiza con Gemini."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        temperature=0.5,
        google_api_key=settings.google_api_key,
    )

    target_cat = state.target_category.value if state.target_category else "Diseño Web"
    content_type_val = state.content_type.value if state.content_type else "Consejo"

    # ── 1. Cargar knowledge base completa (incondicional) ────────────────────
    knowledge_docs = _load_full_context()

    # ── 2. Tavily Search (con fallback graceful) ─────────────────────────────
    web_context = await search_market_context(
        target_category=target_cat,
        api_key=settings.tavily_api_key,
    )
    if web_context:
        web_context_section = web_context
    else:
        web_context_section = "(No disponible — el LLM usará su conocimiento de entrenamiento)"

    # ── 3. LLM sintetiza ambas fuentes ───────────────────────────────────────
    prompt = SCOUT_PROMPT_TEMPLATE.format(
        knowledge_docs=knowledge_docs,
        web_context=web_context_section,
        target_date=state.target_date,
        content_type=content_type_val,
        target_category=target_cat,
    )

    response = await llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_IDENTITY),
            HumanMessage(content=prompt),
        ]
    )

    import json

    # response.content puede ser list[dict] con Gemini — extraer texto
    _content = response.content
    raw = (
        "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in _content
        ).strip()
        if isinstance(_content, list)
        else _content.strip()
    )
    # Limpiar posible markdown code block
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        data = json.loads(raw)
        internal_knowledge = data.get("internal_knowledge", "")
        market_context = data.get("market_context", "")
    except json.JSONDecodeError:
        logger.warning("Scout: No se pudo parsear JSON, usando respuesta raw")
        internal_knowledge = raw
        market_context = ""

    source = "Tavily+KB" if web_context else "KB+LLM fallback"
    logger.info(
        "Scout completado [%s]. internal_knowledge: %d chars | market_context: %d chars",
        source, len(internal_knowledge), len(market_context),
    )

    return {
        "internal_knowledge": internal_knowledge,
        "market_context": market_context,
    }
