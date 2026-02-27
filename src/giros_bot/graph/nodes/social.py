"""
Social_Agent — Genera copies para LinkedIn, Instagram y Facebook.
Input: artículo MDX completo desde state.
Output: state.social_assets (SocialAssets).
"""

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ...config import settings
from ...prompts.social import SOCIAL_PROMPT_TEMPLATE
from ...prompts.system import SYSTEM_IDENTITY
from ...schemas.state import AgentState, SocialAssets

logger = logging.getLogger(__name__)


async def social_node(state: AgentState) -> dict:
    """Genera copies para 3 redes sociales desde el artículo base."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        temperature=0.8,
        google_api_key=settings.google_api_key,
    )

    # URL final del post (debe coincidir con publisher: YYYY-MM-{slug})
    from datetime import datetime
    date_prefix = datetime.strptime(state.target_date, "%Y-%m-%d").strftime("%Y-%m")
    post_url = f"https://girosmedia.cl/blog/{date_prefix}-{state.slug}"

    prompt = SOCIAL_PROMPT_TEMPLATE.format(
        title=state.title,
        description=state.description,
        pain_point=state.pain_point,
        hook_angle=state.hook_angle,
        key_takeaway=state.key_takeaway,
        editorial_brief=state.editorial_brief,
        hero_product=state.hero_product,
    )

    response = await llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_IDENTITY),
            HumanMessage(content=prompt),
        ]
    )

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
        logger.error("Social: LLM devolvió respuesta vacía. Prompt: %s", prompt[:200])
        raise ValueError("Social_Agent: respuesta vacía del LLM")

    data = json.loads(raw)

    # Inyectar URL programáticamente — no depender del LLM para esto
    linkedin = data.get("linkedin_copy", "").strip()
    facebook = data.get("facebook_copy", "").strip()
    instagram = data.get("instagram_copy", "").strip()

    url_pattern = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

    def _contains_url(text: str) -> bool:
        return bool(url_pattern.search(text))

    linkedin_final = linkedin if _contains_url(linkedin) else f"{linkedin}\n\n🔗 {post_url}"
    facebook_final = facebook if _contains_url(facebook) else f"{facebook}\n\n{post_url}"
    # Instagram: el link va en bio, no en el copy

    social_assets = SocialAssets(
        linkedin_copy=linkedin_final,
        instagram_copy=instagram,
        facebook_copy=facebook_final,
        short_url=post_url,
    )

    logger.info("Social completado. LinkedIn: %d chars", len(social_assets.linkedin_copy))

    return {"social_assets": social_assets}
