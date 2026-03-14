"""Tests del Scheduler_Node (sin LLM, lógica pura)."""

import pytest

from src.giros_bot.publication.nodes.scheduler import (
    CATEGORY_ROTATION,
    FORMAT_ROTATION,
    scheduler_node,
)
from src.giros_bot.schemas.state import AgentState, ArticleFormat, ContentType, FrontendCategory


# ── ContentType: siempre CONSEJO independiente del día ──────────────────────

@pytest.mark.asyncio
async def test_scheduler_siempre_consejo_lunes():
    state = AgentState(target_date="2026-02-23")  # Lunes
    result = await scheduler_node(state)
    assert result["content_type"] == ContentType.CONSEJO


@pytest.mark.asyncio
async def test_scheduler_siempre_consejo_martes():
    state = AgentState(target_date="2026-02-24")  # Martes (antes VENTA, ahora siempre CONSEJO)
    result = await scheduler_node(state)
    assert result["content_type"] == ContentType.CONSEJO


@pytest.mark.asyncio
async def test_scheduler_siempre_consejo_jueves():
    state = AgentState(target_date="2026-02-26")  # Jueves (antes VENTA, ahora siempre CONSEJO)
    result = await scheduler_node(state)
    assert result["content_type"] == ContentType.CONSEJO


# ── Categoría y formato: rotación determinista ───────────────────────────────

@pytest.mark.asyncio
async def test_scheduler_retorna_categoria():
    state = AgentState(target_date="2026-02-23")
    result = await scheduler_node(state)
    assert result["target_category"] in CATEGORY_ROTATION


@pytest.mark.asyncio
async def test_scheduler_retorna_article_format():
    state = AgentState(target_date="2026-02-23")
    result = await scheduler_node(state)
    assert result["article_format"] in FORMAT_ROTATION


@pytest.mark.asyncio
async def test_scheduler_rotacion_cubre_todas_categorias():
    """6 días consecutivos deben cubrir las 6 categorías exactamente una vez."""
    from datetime import date, timedelta
    start = date(2026, 1, 1)
    categorias = set()
    for i in range(6):
        d = (start + timedelta(days=i)).isoformat()
        result = await scheduler_node(AgentState(target_date=d))
        categorias.add(result["target_category"])
    assert len(categorias) == 6


@pytest.mark.asyncio
async def test_scheduler_rotacion_cubre_todos_formatos():
    """5 días consecutivos deben cubrir los 5 formatos exactamente una vez."""
    from datetime import date, timedelta
    start = date(2026, 1, 1)
    formatos = set()
    for i in range(5):
        d = (start + timedelta(days=i)).isoformat()
        result = await scheduler_node(AgentState(target_date=d))
        formatos.add(result["article_format"])
    assert len(formatos) == 5


@pytest.mark.asyncio
async def test_scheduler_misma_fecha_mismo_resultado():
    """La rotación es determinista: misma fecha → mismo resultado."""
    state = AgentState(target_date="2026-03-15")
    r1 = await scheduler_node(state)
    r2 = await scheduler_node(state)
    assert r1["target_category"] == r2["target_category"]
    assert r1["article_format"] == r2["article_format"]


# ── Overrides del state ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scheduler_respeta_override_categoria():
    state = AgentState(
        target_date="2026-02-23",
        target_category=FrontendCategory.MARKETING,
    )
    result = await scheduler_node(state)
    assert result["target_category"] == FrontendCategory.MARKETING


@pytest.mark.asyncio
async def test_scheduler_respeta_override_formato():
    state = AgentState(
        target_date="2026-02-23",
        article_format=ArticleFormat.CASE_STUDY,
    )
    result = await scheduler_node(state)
    assert result["article_format"] == ArticleFormat.CASE_STUDY
