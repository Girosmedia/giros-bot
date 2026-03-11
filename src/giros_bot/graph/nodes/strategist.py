"""
Strategist_Agent — Selecciona formato editorial, tópico, categoría frontend, slug y tags.
Produce un editorial_brief adaptado al article_format elegido basándose en la inspiración del Scout.
"""

import json
import logging
import random

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from giros_bot.config import settings
from giros_bot.prompts.strategist import STRATEGIST_PROMPT_TEMPLATE
from giros_bot.prompts.system import SYSTEM_IDENTITY
from giros_bot.schemas.state import AgentState, ArticleFormat, FrontendCategory

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {cat.value for cat in FrontendCategory}
VALID_FORMATS = {fmt.value for fmt in ArticleFormat}

# Formatos con pesos para rotación ponderada.
FORMAT_WEIGHTS = {
    "guide": 4,      # Guías paso a paso (alto valor)
    "comparison": 4, # Comparativas (muy útil para decidir)
    "tips": 3,       # Consejos rápidos
    "case_study": 2, # Historias de éxito
    "listicle": 1,   # Listas (menos peso para evitar repetición)
}


def _generate_format_hint() -> str:
    """Genera un hint de formato sugerido, ponderado para forzar diversidad."""
    formats = list(FORMAT_WEIGHTS.keys())
    weights = [FORMAT_WEIGHTS[f] for f in formats]
    suggested = random.choices(formats, weights=weights, k=1)[0]
    return f"Formato sugerido para este post: {suggested}."


async def strategist_node(state: AgentState) -> dict:
    """Determina tópico, categoría, slug y tags para el artículo de consejos."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview", # Cerebro estratégico de última generación
        temperature=1.0,   # Creatividad máxima para estrategia
        google_api_key=settings.google_api_key,
    )

    # target_category viene del Scheduler
    target_cat = state.target_category.value if state.target_category else "Marketing Digital"

    # Format hint para forzar diversidad
    format_hint = _generate_format_hint()
    logger.info("Strategist: format_hint = %s", format_hint)

    prompt = STRATEGIST_PROMPT_TEMPLATE.format(
        target_date=state.target_date,
        content_type="Consejo", # Forzado por el nuevo flujo
        internal_knowledge=state.internal_knowledge[:2000],
        market_context=state.market_context[:2000],
        target_category=target_cat,
        format_hint=format_hint,
        recent_history_context=state.recent_history_context,
    )

    response = await llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_IDENTITY),
            HumanMessage(content=prompt),
        ]
    )

    # Limpieza y parseo de JSON
    content = response.content
    raw = (
        "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ).strip()
        if isinstance(content, list)
        else content.strip()
    )
    
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].strip()

    if not raw:
        logger.error("Strategist: LLM devolvió respuesta vacía")
        raise ValueError("Strategist_Agent: respuesta vacía del LLM")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Strategist: Error al parsear JSON: %s. Raw: %s", e, raw)
        raise

    # La categoría del Scheduler manda
    frontend_category = state.target_category or FrontendCategory(data.get("frontend_category", "Marketing Digital"))

    # Validar article_format
    raw_format = data.get("article_format", "tips")
    if raw_format not in VALID_FORMATS:
        logger.warning("Strategist: formato '%s' inválido, fallback a 'tips'", raw_format)
        raw_format = "tips"
    article_format = ArticleFormat(raw_format)

    # Siempre es 'soft' ya que solo generamos consejos
    selling_intensity = "soft"

    logger.info(
        "Strategist completado: '%s' [%s] | format: %s | slug: %s",
        data.get("topic"),
        frontend_category.value,
        article_format.value,
        data.get("slug"),
    )

    return {
        "frontend_category": frontend_category,
        "article_format":  article_format,
        "slug":            data.get("slug", "articulo-giros-media"),
        "tags":            data.get("tags", []),
        "title":           data.get("title_hint", ""),
        "target_audience": data.get("target_audience", "Dueño de Pyme en Chile"),
        "pain_point":      data.get("pain_point", ""),
        "hook_angle":      data.get("hook_angle", ""),
        "key_takeaway":    data.get("key_takeaway", ""),
        "editorial_brief": data.get("editorial_brief", ""),
        "hero_product":    data.get("hero_product", "Asesoría Digital Giros Media"),
        "selling_intensity": selling_intensity,
    }
