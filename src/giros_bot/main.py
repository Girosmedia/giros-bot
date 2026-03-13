"""FastAPI entrypoint — Giros Autobot V1.0

Endpoints:
  POST /trigger      → Dispara el pipeline en background (responde 202 inmediatamente).
  POST /run          → Ejecuta el pipeline completo y espera el resultado (síncrono).
  GET  /health       → Health check.
"""

import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import create_async_engine

from .config import settings
from .graph.graph import run_pipeline
from .graph.whatsapp_graph import build_whatsapp_graph
from .integrations.lead import PostgresLeadCapture
from .integrations.scheduling import CalendlyScheduler, GoogleCalendarScheduler
from .integrations.whatsapp_api import WhatsAppAPIMessaging
from .routers.whatsapp import router as whatsapp_router
from .services.history_db import close_db, init_db, save_publication

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la app: conecta y desconecta la BD."""
    # ── Pipeline de contenido ──────────────────────────────────────────────
    await init_db()

    # ── WhatsApp: servicios + grafo ────────────────────────────────────────
    # Guardar settings en app.state para que los routers puedan acceder
    app.state.settings = settings

    # Mensajería
    app.state.messaging_service = WhatsAppAPIMessaging(settings)

    # Agendamiento (intercambiable — cambiar 1 línea para cambiar proveedor)
    if settings.scheduling_provider == "google_calendar":
        app.state.scheduling_service = GoogleCalendarScheduler()
    else:
        app.state.scheduling_service = CalendlyScheduler(settings.scheduling_url)

    # Captura de leads (PostgreSQL)
    _wa_engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    lead_service = PostgresLeadCapture(_wa_engine)
    await lead_service.init_table()
    app.state.lead_service = lead_service

    # Anti-duplicados en memoria (se reinicia con el proceso — suficiente para MVP)
    app.state.processed_message_ids = set()

    # Grafo LangGraph con checkpointer PostgreSQL
    _wa_saver_cm = None
    checkpointer = None
    try:
        from contextlib import AsyncExitStack

        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # AsyncPostgresSaver (psycopg3) necesita "postgresql://...", no "postgresql+asyncpg://..."
        pg_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        _wa_saver_cm = AsyncExitStack()
        checkpointer = await _wa_saver_cm.enter_async_context(
            AsyncPostgresSaver.from_conn_string(pg_url)
        )
        await checkpointer.setup()
    except Exception as e:
        logger.warning(
            "No se pudo inicializar AsyncPostgresSaver: %s. "
            "Usando MemorySaver (sin persistencia entre reinicios).",
            e,
        )
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()

    app.state.whatsapp_graph = build_whatsapp_graph(
        checkpointer=checkpointer,
        scheduling_service=app.state.scheduling_service,
        lead_service=lead_service,
    )
    logger.info("WhatsApp graph inicializado. scheduling_provider=%s", settings.scheduling_provider)

    yield

    # ── Cleanup ────────────────────────────────────────────────────────────
    await close_db()
    await _wa_engine.dispose()
    if _wa_saver_cm is not None:
        await _wa_saver_cm.aclose()


app = FastAPI(
    title="Giros Autobot",
    description="Sistema de generación de contenido automatizado para Giros Media SpA",
    version="1.0.0",
    lifespan=lifespan,
)

# Router para la V1
v1_router = APIRouter(prefix="/v1")

class RunRequest(BaseModel):
    target_date: str = Field(
        default_factory=lambda: date.today().isoformat(),
        description="Fecha objetivo en formato YYYY-MM-DD. Default: hoy.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )

class RunResponse(BaseModel):
    target_date:    str
    content_type:   str
    title:          str
    slug:           str
    category:       str
    quality_score:  int
    mdx_preview:    str  # Primeros 500 chars del MDX
    social_assets:  dict | None
    image_prompt:   str
    error_message:  str

@app.get("/health")
async def health():
    return {"status": "ok", "service": "giros-autobot", "version": "1.0.0"}

async def _run_pipeline_background(target_date: str) -> None:
    """Tarea de background: ejecuta el pipeline completo sin bloquear la respuesta HTTP."""
    try:
        logger.info("Background pipeline iniciado para %s", target_date)
        state = await run_pipeline(target_date)
        logger.info(
            "Background pipeline completado. slug=%s quality=%d",
            state.get("slug"), state.get("quality_score", 0),
        )
        # Guardar en base de datos historial si hay slug
        if state.get("slug"):
            _fc = state.get("frontend_category")
            _af = state.get("article_format")
            await save_publication({
                "target_date": state.get("target_date", ""),
                "slug": state.get("slug", ""),
                "category": _fc.value if _fc is not None else "",
                "topic": state.get("title", ""),
                "format": _af.value if _af is not None else "",
                "visual_style": state.get("visual_style", ""),
                "image_prompt": state.get("image_prompt", ""),
                "image_alt": state.get("image_alt", "")
            })
    except Exception as e:
        logger.exception("Background pipeline falló para %s: %s", target_date, e)

class PostConsejosRequest(BaseModel):
    target_date: str = Field(
        default_factory=lambda: date.today().isoformat(),
        description="Fecha objetivo YYYY-MM-DD. Default: hoy.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )

@v1_router.post("/post-consejos", status_code=202, tags=["Contenido RRSS"])
async def post_consejos_endpoint(request: PostConsejosRequest, background_tasks: BackgroundTasks):
    """Genera y publica contenido de consejos para RRSS en background."""
    logger.info("POST /v1/post-consejos → target_date=%s", request.target_date)
    background_tasks.add_task(_run_pipeline_background, request.target_date)
    return {
        "status": "accepted",
        "target_date": request.target_date,
        "message": "Pipeline de consejos iniciado en background. El proceso notificará al finalizar.",
    }

@v1_router.post("/run", response_model=RunResponse, tags=["Admin"])
async def run_pipeline_endpoint(request: RunRequest):
    """Ejecuta el pipeline completo: genera y publica artículo + assets sociales (Síncrono)."""
    logger.info("POST /v1/run → target_date=%s", request.target_date)

    try:
        state = await run_pipeline(request.target_date)
        
        # Guardar en base de datos historial
        if state.get("slug"):
            _fc = state.get("frontend_category")
            _af = state.get("article_format")
            await save_publication({
                "target_date": state.get("target_date", ""),
                "slug": state.get("slug", ""),
                "category": _fc.value if _fc is not None else "",
                "topic": state.get("title", ""),
                "format": _af.value if _af is not None else "",
                "visual_style": state.get("visual_style", ""),
                "image_prompt": state.get("image_prompt", ""),
                "image_alt": state.get("image_alt", "")
            })
            
    except Exception as e:
        logger.exception("Error en pipeline")
        raise HTTPException(status_code=500, detail=str(e)) from e

    social = state.get("social_assets")
    _ct  = state.get("content_type")
    _fc2 = state.get("frontend_category")
    return RunResponse(
        target_date=   state.get("target_date", ""),
        content_type=  _ct.value if _ct is not None else "",
        title=         state.get("title", ""),
        slug=          state.get("slug", ""),
        category=      _fc2.value if _fc2 is not None else "",
        quality_score= state.get("quality_score", 0),
        mdx_preview=   state.get("mdx_content_body", "")[:500],
        social_assets= social.model_dump() if social else None,
        image_prompt=  state.get("image_prompt", ""),
        error_message= state.get("error_message", ""),
    )

app.include_router(v1_router)
app.include_router(whatsapp_router)
