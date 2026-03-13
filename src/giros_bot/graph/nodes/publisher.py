"""
Publisher_Agent — Commit MDX + imagen a GitHub + publicación directa en RRSS.

Acciones:
  1. Commit atómico (Git Trees API) con MDX + imagen SIN watermark → blog web.
  2. Aplicar watermark en memoria (imagen para RRSS).
  3. Subir imagen con watermark a Cloudflare R2 → obtener presigned URL.
  4. Publicar en RRSS (FB, IG, LinkedIn) usando la presigned URL y/o bytes directos.

Sin polling. La publicación en RRSS es inmediata tras el commit a GitHub.
"""

import asyncio
import base64
import logging
import time
from datetime import datetime

from github import Github, GithubException, InputGitTreeElement

from ...config import settings
from ...schemas.state import AgentState, SocialAssets
from ...services.social.base import SocialPayload
from ...services.social.dispatcher import social_dispatcher

logger = logging.getLogger(__name__)

_GH_REF_RETRIES = 3  # Reintentos para actualizar la ref (non-fast-forward)


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
        img_blob = repo.create_git_blob(base64.b64encode(img_bytes).decode("utf-8"), "base64")
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
            base_tree = repo.get_git_tree(base_tree_sha)

            new_tree = repo.create_git_tree(tree_elements, base_tree)
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

    assert last_exc is not None
    raise last_exc


def _upload_to_r2_sync(image_bytes: bytes, filename: str) -> str:
    """
    Sube la imagen watermarked a Cloudflare R2 y retorna una presigned URL.
    Operación síncrona — invocar con asyncio.to_thread().
    """
    from ...services.social.r2_uploader import upload_image_to_r2

    return upload_image_to_r2(image_bytes, filename)


def _cleanup_r2_sync() -> None:
    """Limpieza lazy de imágenes antiguas en R2. Invocada en background."""
    from ...services.social.r2_uploader import cleanup_old_social_images

    cleanup_old_social_images()


async def publisher_node(state: AgentState) -> dict:
    """
    Publica MDX + imagen (sin watermark) en GitHub y distribuye en RRSS
    con la imagen watermarked subida directamente a Cloudflare R2.
    No hay polling: la publicación en RRSS es inmediata.
    """
    results = {}
    date_prefix = datetime.strptime(state.target_date, "%Y-%m-%d").strftime("%Y-%m")
    full_slug = f"{date_prefix}-{state.slug}"
    post_url = f"https://girosmedia.cl/blog/{full_slug}"

    # URL del CDN de Vercel — solo para referencia en logs/resultados, no se usa en RRSS
    image_cdn_url = f"https://girosmedia.cl/blog/{state.slug}.jpg" if state.image_bytes_b64 else ""

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

    # ── 1. Commit atómico a GitHub (MDX + imagen SIN watermark) ────────────
    try:
        await asyncio.to_thread(
            _commit_to_github_sync,
            mdx_final,
            mdx_path,
            img_path,
            state.image_bytes_b64 or "",
            commit_msg,
        )
        results["image_url_generated"] = image_cdn_url

        if state.social_assets:
            state.social_assets.short_url = post_url

    except Exception as e:
        logger.error("Publisher: error GitHub → %s: %s", type(e).__name__, e, exc_info=True)
        results["error_message"] = f"GitHub error: {type(e).__name__}: {e}"
        return results

    # ── 2. Publicación en RRSS ──────────────────────────────────────────────
    if not state.social_assets:
        logger.info("Publisher: sin social_assets, omitiendo publicación en RRSS.")
        return results

    # 2a. Aplicar watermark en memoria
    watermarked_b64 = state.image_bytes_b64
    r2_image_url = ""

    if state.image_bytes_b64:
        logger.info("Publisher: aplicando marca de agua para RRSS...")
        from ...services.social.watermark import apply_watermark_to_b64

        watermarked_b64 = await asyncio.to_thread(
            apply_watermark_to_b64,
            state.image_bytes_b64,
        )

        # 2b. Subir imagen watermarked a R2 → obtener presigned URL para FB e IG
        try:
            logger.info("Publisher: subiendo imagen watermarked a Cloudflare R2...")
            watermarked_bytes = base64.b64decode(watermarked_b64)
            r2_filename = f"{state.slug}.jpg"
            r2_image_url = await asyncio.to_thread(
                _upload_to_r2_sync, watermarked_bytes, r2_filename
            )
            logger.info("Publisher: imagen disponible en R2 (presigned URL generada).")

            # 2c. Limpieza lazy de imágenes antiguas en R2 (en background, no bloquea)
            asyncio.create_task(asyncio.to_thread(_cleanup_r2_sync))

        except Exception as e:
            logger.error(
                "Publisher: error al subir imagen a R2 → %s: %s", type(e).__name__, e, exc_info=True
            )
            # No bloqueamos la publicación: LinkedIn puede continuar con bytes directos,
            # pero FB e IG fallarán gracefully desde su propio publisher.

    # 2d. Construir payload y publicar en todas las plataformas
    # state.social_assets ya está validado como no-None por el guard de la línea 176.
    assert isinstance(state.social_assets, SocialAssets)
    payload = SocialPayload(
        social_assets=state.social_assets,
        image_url=r2_image_url,  # Presigned URL de R2 → usada por FB e IG
        post_url=post_url,
        image_prompt=state.image_prompt,
        image_bytes_b64=watermarked_b64,  # Bytes con watermark → usados por LinkedIn
    )

    await social_dispatcher.publish_all(payload)

    return results
