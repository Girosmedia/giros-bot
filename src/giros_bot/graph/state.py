"""
TypedDict wrapper para LangGraph StateGraph.
LangGraph requiere TypedDict (no BaseModel) como tipo de estado del grafo.
AgentStateDict es un espejo de AgentState como TypedDict.
"""

from typing import Any, TypedDict


class AgentStateDict(TypedDict, total=False):
    """Estado del grafo compatible con LangGraph StateGraph."""
    # Contexto inicial
    target_date:        str
    content_type:       Any | None   # ContentType enum
    target_category:    Any | None   # FrontendCategory forzada por rotación semanal

    # Investigación
    market_context:     str
    internal_knowledge: str

    # Generación web
    title:              str
    slug:               str
    frontend_category:  Any | None   # FrontendCategory enum
    tags:               list
    description:        str
    mdx_content_body:   str

    # Social
    social_assets:      Any | None   # SocialAssets

    # Visual
    image_prompt:       str
    image_alt:          str
    image_url_generated: str
    image_bytes_b64:    str   # Imagen Imagen 3 en base64

    # Estrategia editorial
    article_format:     Any | None   # ArticleFormat enum
    target_audience:    str
    pain_point:         str
    hook_angle:         str
    key_takeaway:       str
    editorial_brief:    str
    hero_product:       str
    selling_intensity:  str

    # Control
    quality_score:      int
    retry_count:        int
    error_message:      str
