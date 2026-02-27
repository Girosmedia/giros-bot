"""
Publisher_Agent — Commit MDX + imagen a GitHub en UN SOLO COMMIT + POST webhook RRSS.

Acciones:
  1. Commit atómico (Git Trees API) con MDX + imagen juntos → 1 solo deploy.
  2. Espera (polling) hasta que la imagen esté disponible en producción.
  3. POST webhook con payload { social_assets, image_url, post_url }.
"""

import asyncio
import base64
import logging
import time
from datetime import datetime

import httpx
from github import Github, GithubException, InputGitTreeElement

from ...config import settings
from ...schemas.state import AgentState
from ...services.social.base import SocialPayload
from ...services.social.dispatcher import social_dispatcher

logger = logging.getLogger(__name__)

IMAGE_POLL_RETRIES = 20    # Máximo de intentos
IMAGE_POLL_INTERVAL = 15   # Segundos entre intentos
_GH_REF_RETRIES = 3        # Reintentos para actualizar la ref (non-fast-forward)


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


def _commit_to_github_sync(
    mdx_final: str,
    mdx_path: str,
    img_path: str,
    image_bytes_b64: str,
    commit_msg: str,
) -> str:
    """
    Ejecuta el commit atómico via Git Trees API (operación síncrona).
    Se invoca desde publisher_node mediante asyncio.to_thread() para no bloquear
    el event loop.

    Incluye retry con backoff exponencial para manejar errores non-fast-forward
    causados por commits concurrentes en la rama main.

    Returns:
        SHA del nuevo commit creado.
    Raises:
        GithubException: Si todos los reintentos fallan.
    """
    gh = Github(settings.github_token)
    repo = gh.get_repo(f"{settings.github_repo_owner}/{settings.github_repo_name}")

    # Crear blobs primero — son independientes del HEAD actual y pueden reutilizarse
    # en cada reintento sin volver a subir el contenido.
    mdx_blob = repo.create_git_blob(mdx_final, "utf-8")
    tree_elements = [
        InputGitTreeElement(path=mdx_path, mode="100644", type="blob", sha=mdx_blob.sha)
    ]

    if image_bytes_b64:
        img_bytes = base64.b64decode(image_bytes_b64)
        img_blob = repo.create_git_blob(
            base64.b64encode(img_bytes).decode("utf-8"), "base64"
        )
        tree_elements.append(
            InputGitTreeElement(path=img_path, mode="100644", type="blob", sha=img_blob.sha)
        )

    last_exc: GithubException | None = None

    for attempt in range(1, _GH_REF_RETRIES + 1):
        try:
            # Re-fetch la ref en cada intento para obtener el HEAD más reciente
            # y evitar errores non-fast-forward cuando la rama fue actualizada
            # entre intentos (o durante el procesamiento de la pipeline).
            main_ref = repo.get_git_ref("heads/main")
            parent_commit = repo.get_git_commit(main_ref.object.sha)
            base_tree_sha = parent_commit.tree.sha

            new_tree = repo.create_git_tree(tree_elements, base_tree_sha)
            new_commit = repo.create_git_commit(
                message=commit_msg,
                tree=new_tree,
                parents=[parent_commit],
            )
            main_ref.edit(new_commit.sha)
            logger.info(
                "GitHub: commit único (MDX + imagen) → %s [%s]",
                new_commit.sha[:7],
                mdx_path,
            )
            return new_commit.sha

        except GithubException as exc:
            last_exc = exc
            logger.warning(
                "Publisher: intento %d/%d fallido al actualizar ref — %s: %s",
                attempt,
                _GH_REF_RETRIES,
                type(exc).__name__,
                exc,
            )
            if attempt < _GH_REF_RETRIES:
                time.sleep(2**attempt)  # Backoff exponencial: 2s, 4s, …

    assert last_exc is not None  # El bucle siempre ejecuta al menos una iteración
    raise last_exc


async def publisher_node(state: AgentState) -> dict:
    """Publica MDX + imagen en GitHub en UN SOLO commit atómico y dispara el webhook de RRSS."""
    results = {}
    date_prefix = datetime.strptime(state.target_date, "%Y-%m-%d").strftime("%Y-%m")
    full_slug = f"{date_prefix}-{state.slug}"
    post_url = f"https://girosmedia.cl/blog/{full_slug}"
    image_public_url = f"https://girosmedia.cl/blog/{state.slug}.jpg" if state.image_bytes_b64 else ""

    mdx_path = f"content/blog/{full_slug}.mdx"
    img_path = f"public/blog/{state.slug}.jpg"

    # Inyectar image_alt real del Visual Agent (el Writer deja __IMAGE_ALT__ como placeholder)
    mdx_final = state.mdx_content_body.replace(
        "__IMAGE_ALT__",
        state.image_alt or f"Imagen de portada para: {state.title}",
    )

    if not state.image_bytes_b64:
        logger.warning("Publisher: sin imagen generada, el post irá sin imagen.")

    commit_msg = f"content(blog): {state.title} [{state.target_date}]"

    try:
        # Ejecutar todas las llamadas síncronas de PyGithub en un hilo separado
        # para no bloquear el event loop de asyncio.
        await asyncio.to_thread(
            _commit_to_github_sync,
            mdx_final,
            mdx_path,
            img_path,
            state.image_bytes_b64 or "",
            commit_msg,
        )

        results["image_url_generated"] = image_public_url

        if state.social_assets:
            state.social_assets.short_url = post_url

    except Exception as e:
        logger.error("Publisher: error GitHub → %s: %s", type(e).__name__, e, exc_info=True)
        results["error_message"] = f"GitHub error: {type(e).__name__}: {e}"
        return results

    # ── 3. Webhook RRSS (espera imagen disponible primero) ──────────────────
    if state.social_assets:
        # Esperar a que Vercel/CDN despliegue la imagen antes de publicar
        if image_public_url:
            await _wait_for_image(image_public_url)

        payload = SocialPayload(
            social_assets=state.social_assets,
            image_url=image_public_url,
            post_url=post_url,
            image_prompt=state.image_prompt,
            image_bytes_b64=state.image_bytes_b64
        )
        
        # El dispatcher se encarga de enviar a Make.com (y futuros conectores)
        await social_dispatcher.publish_all(payload)

    return results
