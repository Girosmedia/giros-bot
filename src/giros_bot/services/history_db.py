"""
Capa de acceso a datos para el historial de publicaciones.
Motor: PostgreSQL (asyncpg dialect) vía SQLAlchemy 2.0 async ORM.
"""

import logging
from datetime import datetime
from typing import TypedDict

from sqlalchemy import String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..config import settings

logger = logging.getLogger(__name__)


# ── ORM Base & Modelo ────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class Publication(Base):
    __tablename__ = "publications"

    id:           Mapped[int]      = mapped_column(primary_key=True, autoincrement=True)
    target_date:  Mapped[str]      = mapped_column(String(10), nullable=False)
    slug:         Mapped[str]      = mapped_column(String(255), nullable=False)
    category:     Mapped[str]      = mapped_column(String(100), nullable=False)
    topic:        Mapped[str]      = mapped_column(String(500), nullable=False)
    format:       Mapped[str]      = mapped_column(String(50), nullable=False)
    visual_style: Mapped[str]      = mapped_column(String(100), nullable=False, default="")
    image_prompt: Mapped[str]      = mapped_column(Text, nullable=False)
    image_alt:    Mapped[str]      = mapped_column(String(500), nullable=False)
    created_at:   Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


# ── Tipo público para callers ────────────────────────────────────────────────

class PublicationRecord(TypedDict):
    target_date:  str
    slug:         str
    category:     str
    topic:        str
    format:       str
    visual_style: str
    image_prompt: str
    image_alt:    str


# ── Engine & Session factory (singletons) ────────────────────────────────────

_engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
_async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine, expire_on_commit=False
)


# ── API pública ──────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Crea la tabla publications si no existe. Llamar una sola vez en el lifespan de FastAPI."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Base de datos PostgreSQL inicializada (tabla publications lista).")


async def close_db() -> None:
    """Cierra el pool de conexiones. Llamar en el shutdown del lifespan."""
    await _engine.dispose()
    logger.info("Pool de conexiones PostgreSQL cerrado.")


async def save_publication(data: PublicationRecord) -> None:
    """Persiste un registro de publicación exitosa."""
    try:
        async with _async_session() as session:
            session.add(Publication(
                target_date=  data["target_date"],
                slug=         data["slug"],
                category=     data["category"],
                topic=        data["topic"],
                format=       data["format"],
                visual_style= data.get("visual_style", ""),
                image_prompt= data["image_prompt"],
                image_alt=    data["image_alt"],
            ))
            await session.commit()
        logger.info("Publicación '%s' (%s) guardada en PostgreSQL.", data["slug"], data["target_date"])
    except Exception as e:
        logger.error("Error al guardar publicación en PostgreSQL: %s", e)


async def get_recent_history(limit: int = 10) -> list[PublicationRecord]:
    """Retorna las últimas N publicaciones ordenadas por fecha descendente."""
    try:
        async with _async_session() as session:
            result = await session.execute(
                select(Publication)
                .order_by(Publication.target_date.desc(), Publication.id.desc())
                .limit(limit)
            )
            rows = result.scalars().all()
        return [
            PublicationRecord(
                target_date=  row.target_date,
                slug=         row.slug,
                category=     row.category,
                topic=        row.topic,
                format=       row.format,
                visual_style= row.visual_style,
                image_prompt= row.image_prompt,
                image_alt=    row.image_alt,
            )
            for row in rows
        ]
    except Exception as e:
        logger.error("Error al leer historial desde PostgreSQL: %s", e)
        return []


async def get_history_context_text(limit: int = 10) -> str:
    """
    Formatea el historial reciente para inyectarlo en Scout y Strategist.
    Ayuda a evitar repetir títulos y temas.
    """
    history = await get_recent_history(limit)
    if not history:
        return "No hay publicaciones recientes registradas aún."

    lines = ["## ÚLTIMAS PUBLICACIONES (NO REPETIR)"]
    for i, rep in enumerate(history, start=1):
        lines.append(
            f"{i}. Fecha: {rep['target_date']} | Tema: {rep['topic']} "
            f"| Categoría: {rep['category']} | Formato: {rep['format']}"
        )
    return "\n".join(lines)


async def get_visual_history_context_text(limit: int = 10) -> str:
    """
    Formatea el historial reciente enfocado en lo visual para el Visual_Agent.
    Ayuda a alternar estilos, sujetos y ángulos de composición.
    Devuelve sólo estilo y alt (no el prompt completo) para no anclar al LLM
    a los mismos arquetipos de sujeto.
    """
    history = await get_recent_history(limit)
    if not history:
        return "No hay publicaciones visuales recientes registradas aún."

    # Los últimos 3 estilos quedan explícitamente BLOQUEADOS
    blocked_styles = [rep["visual_style"] for rep in history[:3] if rep.get("visual_style")]

    lines = []
    if blocked_styles:
        lines.append(f"🚫 ESTILOS BLOQUEADOS PARA ESTA PUBLICACIÓN (últimos 3 usados): {' | '.join(blocked_styles)}")
        lines.append("Elige un estilo diferente a los anteriores.")
        lines.append("")

    lines.append("## HISTORIAL RECIENTE (estilo → sujeto/escena representada):")
    for rep in history:
        date_str = rep["target_date"]
        style = rep.get("visual_style") or "sin estilo"
        alt = rep.get("image_alt") or "sin descripción"
        lines.append(f"- [{date_str}] {style} → {alt}")

    lines.append("")
    lines.append("Analiza los sujetos del historial y varía: género, edad, tipo de negocio, y si hay persona o no.")
    return "\n".join(lines)
