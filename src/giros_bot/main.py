"""
FastAPI entrypoint — Giros Autobot V1.0

Endpoints:
  POST /trigger      → Dispara el pipeline en background (responde 202 inmediatamente).
  POST /run          → Ejecuta el pipeline completo y espera el resultado (síncrono).
  GET  /health       → Health check.
"""

import logging
from datetime import date

from fastapi import BackgroundTasks, FastAPI, HTTPException, APIRouter
from pydantic import BaseModel, Field

from .graph.graph import run_pipeline
from .services.history_db import save_publication

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Giros Autobot",
    description="Sistema de generación de contenido automatizado para Giros Media SpA",
    version="1.0.0",
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
            save_publication({
                "target_date": state.get("target_date", ""),
                "slug": state.get("slug", ""),
                "category": state.get("frontend_category").value if state.get("frontend_category") else "",
                "topic": state.get("title", ""),
                "format": state.get("article_format").value if state.get("article_format") else "",
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
            save_publication({
                "target_date": state.get("target_date", ""),
                "slug": state.get("slug", ""),
                "category": state.get("frontend_category").value if state.get("frontend_category") else "",
                "topic": state.get("title", ""),
                "format": state.get("article_format").value if state.get("article_format") else "",
                "visual_style": state.get("visual_style", ""),
                "image_prompt": state.get("image_prompt", ""),
                "image_alt": state.get("image_alt", "")
            })
            
    except Exception as e:
        logger.exception("Error en pipeline")
        raise HTTPException(status_code=500, detail=str(e)) from e

    social = state.get("social_assets")
    return RunResponse(
        target_date=   state.get("target_date", ""),
        content_type=  state.get("content_type").value if state.get("content_type") else "",
        title=         state.get("title", ""),
        slug=          state.get("slug", ""),
        category=      state.get("frontend_category").value if state.get("frontend_category") else "",
        quality_score= state.get("quality_score", 0),
        mdx_preview=   state.get("mdx_content_body", "")[:500],
        social_assets= social.model_dump() if social else None,
        image_prompt=  state.get("image_prompt", ""),
        error_message= state.get("error_message", ""),
    )

app.include_router(v1_router)
