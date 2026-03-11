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

    # Contexto Histórico
    recent_history_context: str
    recent_visual_context:  str

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
    social_brief:       str   # Brief narrativo del artículo real → Social_Agent
    visual_brief:       str   # Descripción de escena visual → Visual_Agent

    # Social
    social_assets:      Any | None   # SocialAssets

    # Visual
    visual_style:       str
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
