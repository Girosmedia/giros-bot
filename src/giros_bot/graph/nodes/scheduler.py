"""
Scheduler_Node — Determina ContentType, categoría y formato para cada ejecución.

Regla ContentType:
  Siempre CONSEJO. La lógica CONSEJO/VENTA queda deprecada.

Regla target_category:
  Rotación determinista por día del año (day_of_year % 6).
  Ciclo de 6 días cubre las 6 categorías exactamente una vez → distribución equitativa.
  Período de repetición: 6 días.

Regla article_format:
  Rotación determinista por día del año con período primo respecto a categorías
  (day_of_year % 5). LCM(6, 5) = 30 → 30 días antes de repetir la misma
  combinación categoría+formato. Máxima variedad sin base de datos.

Ambas rotaciones respetan overrides en el state (útil para tests y forzado manual).
"""

import logging
from datetime import datetime

from ...schemas.state import AgentState, ArticleFormat, ContentType, FrontendCategory
from ...services.history_db import get_history_context_text, get_visual_history_context_text, init_db

logger = logging.getLogger(__name__)

# Orden fijo — índice = day_of_year % len(lista)
# LCM(11 categorías, 5 formatos) = 55 días para repetir una combinación exacta.
CATEGORY_ROTATION: list[FrontendCategory] = [
    FrontendCategory.DISENO_WEB,
    FrontendCategory.ECOMMERCE,
    FrontendCategory.SEO_LOCAL,
    FrontendCategory.MARKETING,
    FrontendCategory.PRESENCIA,
    FrontendCategory.MENTALIDAD,
    FrontendCategory.IDENTIDAD,
    FrontendCategory.TECNOLOGIA,
    FrontendCategory.GESTION,
    FrontendCategory.OPORTUNIDADES,
    FrontendCategory.VENTAS,
]

FORMAT_ROTATION: list[ArticleFormat] = [
    ArticleFormat.LISTICLE,
    ArticleFormat.GUIDE,
    ArticleFormat.COMPARISON,
    ArticleFormat.TIPS,
    ArticleFormat.CASE_STUDY,
]


async def scheduler_node(state: AgentState) -> dict:
    """Determina content_type, target_category y article_format según la fecha objetivo."""
    date_obj = datetime.strptime(state.target_date, "%Y-%m-%d")
    day_of_year = date_obj.timetuple().tm_yday  # 1-366

    # ── ContentType: siempre CONSEJO (VENTA deprecado) ──────────────────────
    content_type = state.content_type or ContentType.CONSEJO

    # ── Categoría: rotación determinista, período 6 días ────────────────────
    target_category = state.target_category or CATEGORY_ROTATION[
        (day_of_year - 1) % len(CATEGORY_ROTATION)
    ]

    # ── Formato: rotación determinista, período 5 días (LCM con cat = 30) ───
    article_format = state.article_format or FORMAT_ROTATION[
        (day_of_year - 1) % len(FORMAT_ROTATION)
    ]

    logger.info(
        "Scheduler: %s (%s) → %s | categoría: %s | formato: %s",
        state.target_date,
        date_obj.strftime("%A"),
        content_type.value,
        target_category.value,
        article_format.value,
    )

    # ── Historial: Inicializar DB si no existe y obtener contexto ───────────
    init_db()
    recent_history_context = get_history_context_text(limit=10)
    recent_visual_context = get_visual_history_context_text(limit=10)

    return {
        "content_type":    content_type,
        "target_category": target_category,
        "article_format":  article_format,
        "recent_history_context": recent_history_context,
        "recent_visual_context":  recent_visual_context,
    }
