"""
Validator_Agent — Valida el MDX generado contra PostFrontmatter.
Si quality_score < 7 y retry_count < 2, reenvía al Writer.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from giros_bot.config import settings
from giros_bot.prompts.system import SYSTEM_IDENTITY
from giros_bot.prompts.validator import VALIDATOR_PROMPT_TEMPLATE
from giros_bot.schemas.state import AgentState

logger = logging.getLogger(__name__)


def _has_required_frontmatter(mdx: str) -> bool:
    """Verifica que el frontmatter contenga los campos críticos."""
    required = ["title:", "description:", "date:", "category:", "tags:", "author:"]
    return all(field in mdx for field in required)


async def validator_node(state: AgentState) -> dict:
    """Valida el MDX. Retorna quality_score y posible error_message."""
    # Validación básica sin LLM (rápida)
    if not state.mdx_content_body:
        return {"quality_score": 0, "error_message": "mdx_content_body está vacío"}

    if not state.mdx_content_body.startswith("---"):
        return {
            "quality_score": 2,
            "error_message": "El MDX no comienza con frontmatter YAML (---).",
            "retry_count": state.retry_count + 1,
        }

    if not _has_required_frontmatter(state.mdx_content_body):
        return {
            "quality_score": 3,
            "error_message": "Faltan campos requeridos en el frontmatter.",
            "retry_count": state.retry_count + 1,
        }

    # Validación con LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-lite-latest",
        temperature=0.1,
        google_api_key=settings.google_api_key,
    )

    prompt = VALIDATOR_PROMPT_TEMPLATE.format(
        mdx_content_body=state.mdx_content_body,
        frontend_category=state.frontend_category.value if state.frontend_category else "",
        hero_product=state.hero_product,
        article_format=state.article_format.value if state.article_format else "tips",
        selling_intensity=state.selling_intensity or "soft",
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
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    if not raw:
        logger.error("Validator: LLM devolvió respuesta vacía")
        raise ValueError("Validator_Agent: respuesta vacía del LLM")

    data = json.loads(raw)
    score = int(data.get("quality_score", 5))
    issues = data.get("issues", [])
    error_msg = "; ".join(issues) if issues else ""

    logger.info("Validator: score=%d | issues=%s", score, issues)

    # Incrementar retry_count para que el router pueda limitar los ciclos
    new_retry_count = state.retry_count + 1

    return {
        "quality_score": score,
        "error_message": error_msg,
        "retry_count": new_retry_count,
    }
