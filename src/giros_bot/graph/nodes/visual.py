"""
Visual_Agent — Genera el prompt, el alt text Y la imagen real con Google Imagen 3.

Flujo:
  1. Gemini genera el image_prompt (en inglés) y el image_alt (en español).
  2. Imagen 3 genera la imagen a partir del prompt.
  3. Los bytes de la imagen se guardan en state.image_bytes_b64 (base64).
  4. Publisher_Agent los commitea a public/blog/{slug}.jpg en el repo del frontend.
"""

import base64
import json
import logging

from google import genai
from google.genai import types as genai_types
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ...config import settings
from ...prompts.system import SYSTEM_IDENTITY
from ...prompts.visual import VISUAL_PROMPT_TEMPLATE
from ...schemas.state import AgentState

logger = logging.getLogger(__name__)


async def visual_node(state: AgentState) -> dict:
    """Genera prompt + alt text con Gemini, luego llama a Imagen 3 para generar la imagen."""

    # ── Paso 1: Generar image_prompt e image_alt con Gemini ──────────────────
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-image-preview",
        temperature=0.7,  # Escenas coherentes y realistas, no delirios artísticos
        google_api_key=settings.google_api_key,
    )

    # Resolver content_type a texto legible
    content_type_label = "Consejo" if state.content_type and state.content_type.value == "Consejo" else "Venta"

    # Resolver article_format a texto legible
    article_format_label = state.article_format.value if state.article_format else "tips"

    prompt = VISUAL_PROMPT_TEMPLATE.format(
        title=state.title,
        editorial_brief=state.editorial_brief,
        pain_point=state.pain_point,
        hero_product=state.hero_product or "Presencia Digital para Pymes",
        content_type=content_type_label,
        article_format=article_format_label,
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
        logger.error("Visual: LLM devolvió respuesta vacía. Usando fallback.")
        raise ValueError("Visual_Agent: respuesta vacía del LLM")
    data = json.loads(raw)
    image_prompt = data.get("image_prompt", "")
    image_alt = data.get("image_alt", "")
    logger.info("Visual: prompt generado (%d chars)", len(image_prompt))

    # ── Paso 2: Llamar a gemini-2.5-flash-image (Nano Banana) ────────────
    image_bytes_b64 = ""
    try:
        client = genai.Client(api_key=settings.google_api_key)
        imagen_response = client.models.generate_content(
            model="gemini-2.5-flash-image",
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
            logger.info(
                "Visual: imagen generada con gemini-2.5-flash-image (%d bytes)",
                len(raw_bytes),
            )
        else:
            logger.warning("Visual: gemini-2.5-flash-image no retornó imágenes.")

    except Exception as e:
        logger.warning("Visual: error al generar imagen — %s", e)
        # No falla el pipeline; el artículo se publica sin imagen

    return {
        "image_prompt":    image_prompt,
        "image_alt":       image_alt,
        "image_bytes_b64": image_bytes_b64,
    }
