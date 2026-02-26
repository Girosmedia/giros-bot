"""
Publisher_Agent — Commit MDX + imagen a GitHub + POST webhook RRSS.

Acciones:
  1. Commit del archivo .mdx a /content/blog/{YYYY-MM}-{slug}.mdx.
  2. Commit de la imagen a /public/blog/{slug}.jpg (si existe image_bytes_b64).
  3. Espera (polling) hasta que la imagen esté disponible en producción.
  4. POST webhook con payload { social_assets, image_url, post_url }.
"""

import asyncio
import base64
import logging
from datetime import datetime

import httpx
from github import Github, GithubException

from ...config import settings
from ...schemas.state import AgentState

logger = logging.getLogger(__name__)

IMAGE_POLL_RETRIES = 20    # Máximo de intentos
IMAGE_POLL_INTERVAL = 15   # Segundos entre intentos


async def _wait_for_image(image_url: str) -> bool:
    """Polling hasta que la imagen esté disponible en producción.
    Retorna True si está disponible, False si se agotó el tiempo."""
    full_url = f"https://girosmedia.cl{image_url}" if image_url.startswith("/") else image_url
    logger.info("Publisher: esperando imagen en producción → %s", full_url)

    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in range(1, IMAGE_POLL_RETRIES + 1):
            try:
                r = await client.head(full_url)
                content_type = r.headers.get("content-type", "")
                is_image = r.status_code == 200 and content_type.startswith("image/")
                if is_image:
                    logger.info("Publisher: imagen disponible (intento %d/%d)", attempt, IMAGE_POLL_RETRIES)
                    return True
                logger.info(
                    "Publisher: imagen no disponible aún (HTTP %d, content-type: '%s') — intento %d/%d",
                    r.status_code, content_type, attempt, IMAGE_POLL_RETRIES,
                )
            except httpx.RequestError as e:
                logger.warning("Publisher: error al verificar imagen — %s", e)
            await asyncio.sleep(IMAGE_POLL_INTERVAL)

    logger.warning(
        "Publisher: imagen no apareció tras %ds. Disparando webhook de todas formas.",
        IMAGE_POLL_RETRIES * IMAGE_POLL_INTERVAL,
    )
    return False


async def publisher_node(state: AgentState) -> dict:
    """Publica el MDX + imagen en GitHub y dispara el webhook de RRSS."""
    results = {}
    date_prefix = datetime.strptime(state.target_date, "%Y-%m-%d").strftime("%Y-%m")
    full_slug = f"{date_prefix}-{state.slug}"   # coincide con el nombre de archivo → URL real
    post_url = f"https://girosmedia.cl/blog/{full_slug}"
    image_public_url = f"https://girosmedia.cl/blog/{state.slug}.jpg" if state.image_bytes_b64 else ""

    try:
        gh = Github(settings.github_token)
        repo = gh.get_repo(f"{settings.github_repo_owner}/{settings.github_repo_name}")

        mdx_path = f"content/blog/{full_slug}.mdx"
        img_path = f"public/blog/{state.slug}.jpg"

        # Inyectar image_alt real del Visual Agent (el Writer deja __IMAGE_ALT__ como placeholder)
        mdx_final = state.mdx_content_body.replace(
            "__IMAGE_ALT__",
            state.image_alt or f"Imagen de portada para: {state.title}",
        )

        # ── 1. Commit MDX ────────────────────────────────────────────────────
        commit_msg = f"content(blog): {state.title} [{state.target_date}]"
        try:
            existing = repo.get_contents(mdx_path)
            repo.update_file(
                path=mdx_path,
                message=commit_msg,
                content=mdx_final,
                sha=existing.sha,
                branch="main",
            )
            logger.info("GitHub: MDX actualizado → %s", mdx_path)
        except GithubException:
            repo.create_file(
                path=mdx_path,
                message=commit_msg,
                content=mdx_final,
                branch="main",
            )
            logger.info("GitHub: MDX creado → %s", mdx_path)

        # ── 2. Commit imagen (si Imagen 3 la generó) ─────────────────────────
        if state.image_bytes_b64:
            img_bytes = base64.b64decode(state.image_bytes_b64)
            img_commit_msg = f"assets(blog): imagen para {state.slug}"
            try:
                existing_img = repo.get_contents(img_path)
                repo.update_file(
                    path=img_path,
                    message=img_commit_msg,
                    content=img_bytes,
                    sha=existing_img.sha,
                    branch="main",
                )
                logger.info("GitHub: imagen actualizada → %s", img_path)
            except GithubException:
                repo.create_file(
                    path=img_path,
                    message=img_commit_msg,
                    content=img_bytes,
                    branch="main",
                )
                logger.info("GitHub: imagen creada → %s", img_path)
        else:
            logger.warning("Publisher: sin imagen generada, el post irá sin imagen.")

        results["image_url_generated"] = image_public_url

        if state.social_assets:
            state.social_assets.short_url = post_url

    except Exception as e:
        logger.error("Publisher: error GitHub → %s", e)
        results["error_message"] = f"GitHub error: {e}"
        return results

    # ── 3. Webhook RRSS (espera imagen disponible primero) ──────────────────
    if settings.social_webhook_url and state.social_assets:
        # Esperar a que Vercel/CDN despliegue la imagen antes de llamar a Make
        if image_public_url:
            await _wait_for_image(image_public_url)

        payload = {
            "social_assets": state.social_assets.model_dump(),
            "image_url": image_public_url,
            "post_url": post_url,
            "image_prompt": state.image_prompt,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(settings.social_webhook_url, json=payload)
                response.raise_for_status()
                logger.info("Webhook RRSS disparado. Status: %d", response.status_code)
        except httpx.HTTPError as e:
            logger.warning("Webhook RRSS falló (no crítico): %s", e)

    return results
