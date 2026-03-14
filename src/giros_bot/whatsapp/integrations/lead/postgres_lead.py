"""Implementación PostgresLeadCapture — persiste leads en PostgreSQL.

Tabla: whatsapp_leads
Creada automáticamente en el lifespan de FastAPI (init_whatsapp_db).
Usa el mismo engine asyncpg del proyecto.
"""

import logging
from datetime import datetime

from sqlalchemy import String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ...services.lead_capture import ILeadCaptureService, LeadData

logger = logging.getLogger(__name__)


# ── ORM ──────────────────────────────────────────────────────────────────────

class _LeadBase(DeclarativeBase):
    pass


class WhatsAppLead(_LeadBase):
    __tablename__ = "whatsapp_leads"

    id:             Mapped[int]      = mapped_column(primary_key=True, autoincrement=True)
    phone:          Mapped[str]      = mapped_column(String(30), nullable=False, index=True)
    name:           Mapped[str]      = mapped_column(String(200), nullable=False, default="")
    email:          Mapped[str]      = mapped_column(String(255), nullable=False, default="")
    project_type:   Mapped[str]      = mapped_column(String(100), nullable=False, default="")
    budget_hint:    Mapped[str]      = mapped_column(String(50), nullable=False, default="")
    service_type:   Mapped[str]      = mapped_column(String(50), nullable=False, default="")
    lead_quality:   Mapped[str]      = mapped_column(String(20), nullable=False, default="unknown")
    notes:          Mapped[str]      = mapped_column(Text, nullable=False, default="")
    created_at:     Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


# ── Implementación ────────────────────────────────────────────────────────────

class PostgresLeadCapture:
    """Implementa ILeadCaptureService usando la tabla whatsapp_leads en PostgreSQL."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )

    async def init_table(self) -> None:
        """Crea la tabla whatsapp_leads si no existe. Llamar en el lifespan."""
        async with self._engine.begin() as conn:
            await conn.run_sync(_LeadBase.metadata.create_all)
        logger.info("Tabla whatsapp_leads lista.")

    async def save_lead(self, lead: LeadData) -> bool:
        try:
            async with self._session_factory() as session:
                record = WhatsAppLead(
                    phone=lead.phone,
                    name=lead.name,
                    email=lead.email,
                    project_type=lead.project_type,
                    budget_hint=lead.budget_hint,
                    service_type=lead.service_type,
                    lead_quality=lead.lead_quality,
                    notes=lead.notes,
                )
                session.add(record)
                await session.commit()
                logger.info(
                    "Lead guardado: phone=%s service=%s quality=%s",
                    lead.phone, lead.service_type, lead.lead_quality,
                )
                return True
        except Exception as e:
            logger.error("Error al guardar lead %s: %s", lead.phone, e)
            return False

    async def get_leads_by_phone(self, phone: str) -> list[WhatsAppLead]:
        """Historial de leads del mismo número. Útil para evitar duplicados."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(WhatsAppLead)
                .where(WhatsAppLead.phone == phone)
                .order_by(WhatsAppLead.created_at.desc())
                .limit(10)
            )
            return list(result.scalars().all())


# Verificación estática de Protocol
_: ILeadCaptureService = PostgresLeadCapture.__new__(PostgresLeadCapture)  # type: ignore[assignment]
