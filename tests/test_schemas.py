"""Tests de los schemas Pydantic v2."""

import pytest

from src.giros_bot.schemas.frontend import PostFrontmatter
from src.giros_bot.schemas.state import (
    AgentState,
    ContentType,
    FrontendCategory,
    SocialAssets,
)


def test_content_type_values():
    assert ContentType.CONSEJO.value == "Consejo"
    assert ContentType.VENTA.value == "Venta"


def test_frontend_category_values():
    """Verifica que los valores coincidan exactamente con BlogCategory en el frontend."""
    expected = {
        "Presencia Digital",
        "E-commerce",
        "SEO Local",
        "Marketing Digital",
        "Diseño Web",
        "Mentalidad Emprendedora",
        "Identidad Visual",
        "Tecnología y Herramientas",
        "Gestión de Pymes",
        "Oportunidades y Fondos",
        "Ventas y Fidelización",
    }
    actual = {cat.value for cat in FrontendCategory}
    assert actual == expected


def test_agent_state_defaults():
    state = AgentState(target_date="2026-02-25")
    assert state.content_type is None
    assert state.quality_score == 0
    assert state.retry_count == 0
    assert state.tags == []


def test_agent_state_required_field():
    with pytest.raises(ValueError):
        AgentState()  # target_date es requerido


def test_post_frontmatter_valid():
    fm = PostFrontmatter(
        title="Cómo aparecer en Google Maps: guía para negocios locales en Chile",
        description="Aprende paso a paso cómo registrar y optimizar tu negocio en Google Business Profile para negocios locales.",
        date="2026-02-25",
        category=FrontendCategory.SEO_LOCAL,
        tags=["Google Maps", "SEO Local", "Chile"],
    )
    assert fm.author == "Equipo Giros Media"
    assert fm.category == FrontendCategory.SEO_LOCAL


def test_post_frontmatter_invalid_date():
    with pytest.raises(ValueError):
        PostFrontmatter(
            title="Test",
            description="X" * 120,
            date="25-02-2026",   # formato incorrecto
            category=FrontendCategory.DISENO_WEB,
            tags=["tag1"],
        )


def test_social_assets():
    assets = SocialAssets(
        linkedin_copy="Copy LinkedIn",
        instagram_copy="Copy Instagram #PymesChile",
        facebook_copy="Copy Facebook con link",
        short_url="https://girosmedia.cl/blog/test",
    )
    dumped = assets.model_dump()
    assert "linkedin_copy" in dumped
    assert "short_url" in dumped
