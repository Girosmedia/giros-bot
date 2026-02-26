"""
Strategist_Agent — Selecciona formato editorial, tópico, categoría frontend, slug y tags.
Produce un editorial_brief adaptado al article_format elegido.
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ...config import settings
from ...prompts.strategist import STRATEGIST_PROMPT_TEMPLATE
from ...prompts.system import SYSTEM_IDENTITY
from ...schemas.state import AgentState, ArticleFormat, FrontendCategory

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {cat.value for cat in FrontendCategory}
VALID_FORMATS = {fmt.value for fmt in ArticleFormat}


async def strategist_node(state: AgentState) -> dict:
    """Determina tópico, categoría, slug y tags para el artículo."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-lite-latest",
        temperature=0.85,   # Más creativo para encontrar dolores específicos
        google_api_key=settings.google_api_key,
    )

    # target_category viene del Scheduler (rotación semanal) — es la fuente de verdad
    target_cat = state.target_category.value if state.target_category else "Diseño Web"

    prompt = STRATEGIST_PROMPT_TEMPLATE.format(
        target_date=state.target_date,
        content_type=state.content_type.value if state.content_type else "Consejo",
        internal_knowledge=state.internal_knowledge[:1500],  # Más contexto para argumentos concretos
        market_context=state.market_context[:800],
        target_category=target_cat,
    )

    response = await llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_IDENTITY),
            HumanMessage(content=prompt),
        ]
    )

    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    if not raw:
        logger.error("Strategist: LLM devolvió respuesta vacía")
        raise ValueError("Strategist_Agent: respuesta vacía del LLM")

    data = json.loads(raw)

    # target_category del Scheduler es la fuente de verdad — ignorar lo que diga el LLM
    frontend_category = state.target_category or FrontendCategory(data.get("frontend_category", "Diseño Web"))

    # Validar article_format
    raw_format = data.get("article_format", "tips")
    if raw_format not in VALID_FORMATS:
        logger.warning("Strategist: formato '%s' inválido, fallback a 'tips'", raw_format)
        raw_format = "tips"
    article_format = ArticleFormat(raw_format)

    # selling_intensity: VENTA siempre es hard, CONSEJO siempre es soft
    content_type_str = state.content_type.value if state.content_type else "Consejo"
    selling_intensity = "hard" if content_type_str == "Venta" else "soft"

    logger.info(
        "Strategist: '%s' → %s | format: %s | slug: %s | sell: %s",
        data.get("topic"),
        frontend_category.value,
        article_format.value,
        data.get("slug"),
        selling_intensity,
    )
    logger.info("Strategist brief: %s", data.get("editorial_brief", "")[:200])

    return {
        "frontend_category": frontend_category,
        "article_format":  article_format,
        "slug":            data.get("slug", "articulo-giros-media"),
        "tags":            data.get("tags", []),
        "title":           data.get("title_hint", ""),
        "target_audience": data.get("target_audience", "Dueño de Pyme"),
        "pain_point":      data.get("pain_point", ""),
        "hook_angle":      data.get("hook_angle", ""),
        "key_takeaway":    data.get("key_takeaway", ""),
        "editorial_brief": data.get("editorial_brief", ""),
        "hero_product":    data.get("hero_product", ""),
        "selling_intensity": selling_intensity,
    }
