"""
AgentState y enums canónicos del proyecto.
Este modelo viaja por todos los nodos del grafo LangGraph.

CRÍTICO: FrontendCategory debe coincidir EXACTAMENTE con BlogCategory en types.ts del frontend.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class ContentType(StrEnum):
    """Tipo de contenido según el día de la semana."""
    CONSEJO = "Consejo"   # Lunes / Miércoles / Viernes — Soft Sell
    VENTA = "Venta"       # Martes / Jueves — Hard Sell


class FrontendCategory(StrEnum):
    """
    Categorías de blog.
    Debe coincidir EXACTAMENTE con BlogCategory en types.ts del frontend Next.js.
    """
    PRESENCIA    = "Presencia Digital"
    ECOMMERCE    = "E-commerce"
    SEO_LOCAL    = "SEO Local"
    MARKETING    = "Marketing Digital"
    DISENO_WEB   = "Diseño Web"
    CASOS_EXITO  = "Casos de Éxito"


class ArticleFormat(StrEnum):
    """
    Formato editorial del artículo.
    Determina la estructura del contenido, el estilo visual y el nivel de venta.
    Es INTERNO al bot — NO aparece en el frontmatter del frontend.
    """
    LISTICLE    = "listicle"     # "5 señales...", "7 errores...", lista numerada
    GUIDE       = "guide"        # "Cómo hacer X", paso a paso práctico
    COMPARISON  = "comparison"   # "X vs Y: ¿Cuál necesita tu negocio?"
    TIPS        = "tips"         # "Tips para...", consejos agrupados temáticamente
    CASE_STUDY  = "case_study"   # Historia real/ficticia de transformación, estilo documental


class SocialAssets(BaseModel):
    """Copies para cada red social."""
    linkedin_copy:  str = Field(..., description="Copy profesional para LinkedIn")
    instagram_copy: str = Field(..., description="Copy visual/cercano con hashtags para Instagram")
    facebook_copy:  str = Field(..., description="Copy comunitario con link para Facebook")
    short_url:      str = Field(default="", description="URL del post publicado (se rellena en Publisher)")


class AgentState(BaseModel):
    """
    Estado completo que viaja por todos los nodos de LangGraph.
    Todos los campos tienen defaults para permitir construcción incremental.
    """

    # ── Contexto inicial ─────────────────────────────────────────────────────
    target_date:     str                    = Field(..., description="Fecha objetivo YYYY-MM-DD")
    content_type:    ContentType | None  = None
    target_category: FrontendCategory | None = Field(default=None, description="Categoría forzada por rotación semanal")

    # ── Investigación (Scout_Agent) ──────────────────────────────────────────
    market_context:     str = Field(default="", description="Contexto chileno simulado (noticias, SII, etc.)")
    internal_knowledge: str = Field(default="", description="Extraído de knowledge_base/*.md")

    # ── Generación web (Writer_Agent) ────────────────────────────────────────
    title:             str                          = ""
    slug:              str                          = ""
    frontend_category: FrontendCategory | None  = None
    tags:              list[str]                    = Field(default_factory=list)
    description:       str                          = ""
    mdx_content_body:  str                          = Field(default="", description="Frontmatter YAML + cuerpo MDX completo")

    # ── Generación social (Social_Agent) ─────────────────────────────────────
    social_assets: SocialAssets | None = None

    # ── Visual (Visual_Agent) ────────────────────────────────────────────────
    image_prompt:        str = Field(default="", description="Prompt para generador de imagen (Imagen 3)")
    image_alt:           str = ""
    image_url_generated: str = ""
    image_bytes_b64:     str = Field(default="", description="Imagen generada en base64 para commit en GitHub")

    # ── Estrategia editorial (Strategist_Agent) ──────────────────────────────
    article_format:  ArticleFormat | None = Field(default=None, description="Formato editorial: listicle, guide, comparison, tips, case_study")
    target_audience: str = Field(default="Dueño de Pyme", description="A quién le escribimos")
    pain_point:      str = Field(default="", description="El dolor específico del cliente")
    hook_angle:      str = Field(default="", description="El ángulo editorial directo/controversial")
    key_takeaway:    str = Field(default="", description="La solución única de Giros Media")
    editorial_brief: str = Field(default="", description="Brief editorial adaptado al formato. Para case_study incluye personaje; para otros es temático.")
    hero_product:    str = Field(default="", description="UN solo producto con precio. Ej: Pack Presencia Digital ($290.000 CLP + IVA)")
    selling_intensity: str = Field(default="soft", description="soft = mención al final | hard = argumento de compra explícito")

    # ── Control de calidad (Validator_Agent) ─────────────────────────────────
    quality_score: int = Field(default=0, ge=0, le=10, description="Score 0-10. Retry si < 7")
    retry_count:   int = Field(default=0, ge=0, description="Max 2 retries al Writer")
    error_message: str = ""
