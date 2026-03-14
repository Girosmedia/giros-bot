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
from ..prompts.social import SOCIAL_PROMPT_TEMPLATE
from ...prompts.system import SYSTEM_IDENTITY
from ...schemas.state import AgentState, SocialAssets

logger = logging.getLogger(__name__)


async def social_node(state: AgentState) -> dict:
    """Genera copies para 3 redes sociales desde el artículo base."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview", # Máxima potencia de redacción y persuasión
        temperature=0.7,
        google_api_key=settings.google_api_key,
    )

    # URL final del post
    from datetime import datetime
    date_prefix = datetime.strptime(state.target_date, "%Y-%m-%d").strftime("%Y-%m")
    post_url = f"https://girosmedia.cl/blog/{date_prefix}-{state.slug}"

    # Fallback: si el Writer no extrajo social_brief, armar uno mínimo desde los campos del Strategist
    social_brief = state.social_brief or (
        f"{state.pain_point} {state.key_takeaway} — {state.editorial_brief}"
    ).strip(" —")

    prompt = SOCIAL_PROMPT_TEMPLATE.format(
        title=state.title,
        social_brief=social_brief,
        hero_product=state.hero_product or "Asesoría Digital Giros Media",
    )

    response = await llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_IDENTITY),
            HumanMessage(content=prompt),
        ]
    )

    # Extraer texto limpio
    _content = response.content
    raw = (
        "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in _content
        ).strip()
        if isinstance(_content, list)
        else _content.strip()
    )
    
    # Limpieza de markdown
    if "```" in raw:
        match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        if match:
            raw = match.group(1).strip()
        else:
            raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw)
    except Exception as e:
        logger.error("Social: Error parseando JSON: %s. Raw: %s", e, raw)
        raise ValueError("Social_Agent: Error en el formato de salida del LLM.")

    social_assets = SocialAssets(
        linkedin_copy=data.get("linkedin_copy", "").strip(),
        instagram_copy=data.get("instagram_copy", "").strip(),
        facebook_copy=data.get("facebook_copy", "").strip(),
        short_url=post_url,
    )

    logger.info("Social completado. LinkedIn: %d chars", len(social_assets.linkedin_copy))

    return {"social_assets": social_assets}
