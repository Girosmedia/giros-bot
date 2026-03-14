"""
Writer_Agent — Genera el artículo MDX completo con frontmatter YAML.
Output: mdx_content_body (frontmatter + cuerpo en un solo string).
"""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ...config import settings
from ...prompts.system import SYSTEM_IDENTITY
from ..prompts.writer import WRITER_PROMPT_TEMPLATE
from ...schemas.state import AgentState

logger = logging.getLogger(__name__)


async def writer_node(state: AgentState) -> dict:
    """Genera el artículo MDX completo."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",   # Máxima potencia de redacción y seguimiento de instrucciones
        temperature=0.7,
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

    # Limpieza robusta de bloques de código markdown
    if "```" in mdx_content:
        # Intentamos capturar lo que hay dentro de bloques mdx o md, o simplemente el primer bloque
        match = re.search(r"```(?:mdx|md)?\s*(.*?)```", mdx_content, re.DOTALL)
        if match:
            mdx_content = match.group(1).strip()
        else:
            # Si no hay match pero hay ```, limpiamos manualmente
            mdx_content = mdx_content.replace("```mdx", "").replace("```md", "").replace("```", "").strip()

    # Extraer metadatos del frontmatter de forma más segura
    def extract_yaml_field(field: str, content: str, default: str) -> str:
        pattern = rf"^{field}:\s*[\"']?(.*?)[\"']?\s*$"
        match = re.search(pattern, content, re.MULTILINE)
        return match.group(1).strip() if match else default

    title = extract_yaml_field("title", mdx_content, state.title)
    description = extract_yaml_field("description", mdx_content, state.description)
    social_brief = extract_yaml_field("socialBrief", mdx_content, "")
    visual_brief = extract_yaml_field("visualBrief", mdx_content, "")

    logger.info("Writer completado. MDX: %d chars | title: %s", len(mdx_content), title)
    if not social_brief:
        logger.warning("Writer: socialBrief no encontrado en frontmatter — Social usará campos del Strategist como fallback.")
    if not visual_brief:
        logger.warning("Writer: visualBrief no encontrado en frontmatter — Visual usará campos del Strategist como fallback.")

    return {
        "mdx_content_body": mdx_content,
        "title": title,
        "description": description,
        "social_brief": social_brief,
        "visual_brief": visual_brief,
    }
