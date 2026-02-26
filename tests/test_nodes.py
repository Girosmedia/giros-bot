"""Tests del Scheduler_Node (sin LLM, lógica pura)."""

import pytest

from src.giros_bot.graph.nodes.scheduler import scheduler_node
from src.giros_bot.schemas.state import AgentState, ContentType


@pytest.mark.asyncio
async def test_scheduler_lunes_es_consejo():
    state = AgentState(target_date="2026-02-23")  # Lunes
    result = await scheduler_node(state)
    assert result["content_type"] == ContentType.CONSEJO


@pytest.mark.asyncio
async def test_scheduler_martes_es_venta():
    state = AgentState(target_date="2026-02-24")  # Martes
    result = await scheduler_node(state)
    assert result["content_type"] == ContentType.VENTA


@pytest.mark.asyncio
async def test_scheduler_miercoles_es_consejo():
    state = AgentState(target_date="2026-02-25")  # Miércoles
    result = await scheduler_node(state)
    assert result["content_type"] == ContentType.CONSEJO


@pytest.mark.asyncio
async def test_scheduler_jueves_es_venta():
    state = AgentState(target_date="2026-02-26")  # Jueves
    result = await scheduler_node(state)
    assert result["content_type"] == ContentType.VENTA


@pytest.mark.asyncio
async def test_scheduler_viernes_es_consejo():
    state = AgentState(target_date="2026-02-27")  # Viernes
    result = await scheduler_node(state)
    assert result["content_type"] == ContentType.CONSEJO
