"""
Scheduler_Node — Determina el ContentType y la categoría para cada ejecución.

Regla ContentType (regla de negocio editorial):
  Lunes / Miércoles / Viernes → CONSEJO (educativo, soft sell al cierre)
  Martes / Jueves             → VENTA   (oferta directa, precio explícito)
  Sábado / Domingo            → CONSEJO (fallback)

Regla target_category:
  Aleatoria en cada ejecución → garantiza variedad incluso publicando
  2 artículos el mismo día. Odds de repetir categoría = 1/6.
"""

import logging
import random
from datetime import datetime

from ...schemas.state import AgentState, ContentType, FrontendCategory

logger = logging.getLogger(__name__)

CATEGORY_ROTATION = [
    FrontendCategory.DISENO_WEB,
    FrontendCategory.ECOMMERCE,
    FrontendCategory.SEO_LOCAL,
    FrontendCategory.MARKETING,
    FrontendCategory.PRESENCIA,
    FrontendCategory.CASOS_EXITO,
]


async def scheduler_node(state: AgentState) -> dict:
    """Determina content_type (día semana) y target_category (random) para esta ejecución."""
    date_obj = datetime.strptime(state.target_date, "%Y-%m-%d")
    weekday = date_obj.weekday()  # 0=Lunes … 6=Domingo

    # Martes (1) y Jueves (3) → Rama VENTA
    content_type = ContentType.VENTA if weekday in (1, 3) else ContentType.CONSEJO

    # Categoría aleatoria en cada ejecución
    target_category = random.choice(CATEGORY_ROTATION)

    logger.info(
        "Scheduler: %s (%s) → %s | categoría: %s",
        state.target_date,
        date_obj.strftime("%A"),
        content_type.value,
        target_category.value,
    )

    return {"content_type": content_type, "target_category": target_category}
