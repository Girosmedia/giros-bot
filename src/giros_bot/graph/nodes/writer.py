"""
Writer_Agent — Genera el artículo MDX completo con frontmatter YAML.
Output: mdx_content_body (frontmatter + cuerpo en un solo string).
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ...config import settings
from ...prompts.system import SYSTEM_IDENTITY
from ...prompts.writer import WRITER_PROMPT_TEMPLATE
from ...schemas.state import AgentState

logger = logging.getLogger(__name__)


async def writer_node(state: AgentState) -> dict:
    """Genera el artículo MDX completo."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",   # Modelo potente para redacción de calidad
        temperature=0.75,
        google_api_key=settings.google_api_key,
        max_output_tokens=8192,
    )

    prompt = WRITER_PROMPT_TEMPLATE.format(
        market_context=state.market_context,
        internal_knowledge=state.internal_knowledge,
        target_date=state.target_date,
        content_type=state.content_type.value if state.content_type else "Consejo",
        frontend_category=state.frontend_category.value if state.frontend_category else "Diseño Web",
        title=state.title,
        slug=state.slug,
        tags=state.tags,
        # Datos ricos del Strategist
        article_format=state.article_format.value if state.article_format else "tips",
        target_audience=state.target_audience,
        pain_point=state.pain_point,
        hook_angle=state.hook_angle,
        key_takeaway=state.key_takeaway,
        editorial_brief=state.editorial_brief,
        hero_product=state.hero_product,
        selling_intensity=state.selling_intensity or "soft",
    )

    response = await llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_IDENTITY),
            HumanMessage(content=prompt),
        ]
    )

    # response.content puede ser list[dict] con Gemini — extraer texto
    _raw = response.content
    mdx_content = (
        "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in _raw
        ).strip()
        if isinstance(_raw, list)
        else _raw.strip()
    )
    # El LLM a veces envuelve el output en ```mdx ... ``` — lo eliminamos
    if mdx_content.startswith("```"):
        lines = mdx_content.split("\n")
        # Quitar primera línea (```mdx o ```) y última (```)
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        mdx_content = "\n".join(lines).strip()

    # Extraer el título del frontmatter para actualizar state.title
    title = state.title
    for line in mdx_content.split("\n"):
        if line.startswith("title:"):
            title = line.replace("title:", "").strip().strip('"').strip("'")
            break

    # Extraer description del frontmatter
    description = state.description
    for line in mdx_content.split("\n"):
        if line.startswith("description:"):
            description = line.replace("description:", "").strip().strip('"').strip("'")
            break

    logger.info("Writer completado. MDX: %d chars | title: %s", len(mdx_content), title)

    return {
        "mdx_content_body": mdx_content,
        "title": title,
        "description": description,
    }
