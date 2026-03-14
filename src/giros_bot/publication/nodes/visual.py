"""
Visual_Agent — Genera el prompt, el alt text Y la imagen real con Gemini 3.1 Flash Image.
"""

import base64
import json
import logging
import re

from google import genai
from google.genai import types as genai_types
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ...config import settings
from ...prompts.system import SYSTEM_IDENTITY
from ..prompts.visual import VISUAL_PROMPT_TEMPLATE
from ...schemas.state import AgentState

logger = logging.getLogger(__name__)


async def visual_node(state: AgentState) -> dict:
    """Genera prompt + alt text con Gemini 3, luego llama a Imagen 3.1 para generar la imagen."""

    # ── Paso 1: Generar image_prompt e image_alt con Gemini 3 Flash ─────────
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview", # Máximo razonamiento creativo para dirección de arte
        temperature=1,
        google_api_key=settings.google_api_key,
    )

    # Resolver labels para el prompt
    content_type_label = "Consejo práctico" if state.content_type and state.content_type.value == "Consejo" else "Oportunidad de Negocio"
    article_format_label = state.article_format.value if state.article_format else "tips"

    # Fallback: si el Writer no extrajo visual_brief, armar uno mínimo desde campos del Strategist
    visual_brief = state.visual_brief or (
        f"{state.editorial_brief} — {state.pain_point}"
    ).strip(" —")

    prompt = VISUAL_PROMPT_TEMPLATE.format(
        title=state.title,
        visual_brief=visual_brief,
        hero_product=state.hero_product or "Asesoría Digital Giros Media",
        content_type=content_type_label,
        article_format=article_format_label,
        target_audience=state.target_audience,
        recent_visual_context=state.recent_visual_context,
    )

    response = await llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_IDENTITY),
            HumanMessage(content=prompt),
        ]
    )

    # Extraer JSON de la respuesta
    _content = response.content
    raw = (
        "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in _content
        ).strip()
        if isinstance(_content, list)
        else _content.strip()
    )
    
    # Limpieza de bloques de código markdown
    if "```" in raw:
        match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        if match:
            raw = match.group(1).strip()
        else:
            raw = raw.replace("```json", "").replace("```", "").strip()

    # Fallback values
    visual_style = "Cinematic Realism"
    image_prompt = f"A creative digital art piece about {state.title}. Vibrant magenta colors."
    image_alt = f"Imagen ilustrativa: {state.title}"

    try:
        data = json.loads(raw)
        visual_style = data.get("visual_style", visual_style)
        image_prompt = data.get("image_prompt", image_prompt)
        image_alt = data.get("image_alt", image_alt)
        logger.info("Visual: Prompt artístico generado exitosamente.")
    except Exception as e:
        logger.error("Visual: Error parseando JSON de Gemini: %s. Raw: %s", e, raw)

    # ── Paso 2: Generar imagen real con Gemini 3.1 Flash Image ───────────────
    image_bytes_b64 = ""
    try:
        client = genai.Client(api_key=settings.google_api_key)
        imagen_response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview", 
            contents=[image_prompt],
            config=genai_types.GenerateContentConfig(
                response_modalities=["Image"],
                image_config=genai_types.ImageConfig(
                    aspect_ratio="1:1",
                ),
            ),
        )

        raw_bytes = None
        for part in imagen_response.parts:
            if part.inline_data is not None:
                raw_bytes = part.inline_data.data
                break

        if raw_bytes:
            image_bytes_b64 = base64.b64encode(raw_bytes).decode("utf-8")
            logger.info("Visual: Imagen generada exitosamente (%d bytes)", len(raw_bytes))
        else:
            logger.warning("Visual: El modelo no devolvió bytes de imagen.")

    except Exception as e:
        logger.warning("Visual: Fallo en generación de imagen (3.1 Flash Image) — %s", e)

    return {
        "visual_style":    visual_style,
        "image_prompt":    image_prompt,
        "image_alt":       image_alt,
        "image_bytes_b64": image_bytes_b64,
    }
