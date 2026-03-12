import base64
import logging

import httpx

from giros_bot.config import settings
from .base import ISocialPublisher, SocialPayload, PublishResult

logger = logging.getLogger(__name__)


class FacebookPublisher(ISocialPublisher):
    """
    Conector nativo para publicar en Facebook Pages usando Graph API.

    La imagen se entrega vía URL pública (presigned URL de Cloudflare R2),
    igual que Instagram, para mantener una lógica unificada entre ambas
    plataformas. Meta descarga la imagen desde esa URL al procesar la solicitud.
    """

    @property
    def platform_name(self) -> str:
        return "facebook"

    async def publish(self, payload: SocialPayload) -> PublishResult:
        if not settings.meta_access_token or not settings.facebook_page_id:
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error_message="Credenciales de Meta (Facebook) no configuradas.",
            )

        if not payload.image_url:
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error_message="No hay URL de imagen disponible para publicar en Facebook.",
            )

        url = f"https://graph.facebook.com/v21.0/{settings.facebook_page_id}/photos"
        message = (
            f"{payload.social_assets.facebook_copy}\n\n"
            f"Lee el artículo completo aquí: {payload.post_url}"
        )

        data = {
            "url": payload.image_url,  # Presigned URL de Cloudflare R2 (con watermark)
            "message": message,
            "access_token": settings.meta_access_token,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, data=data)
                response_data = response.json()

                if response.status_code != 200:
                    error_msg = response_data.get("error", {}).get("message", "Error desconocido")
                    logger.error("FacebookPublisher: Error de API: %s", error_msg)
                    return PublishResult(
                        platform=self.platform_name,
                        success=False,
                        error_message=error_msg,
                    )

                post_id = response_data.get("post_id")
                logger.info("FacebookPublisher: Publicado con éxito. Post ID: %s", post_id)
                return PublishResult(
                    platform=self.platform_name,
                    success=True,
                    post_id=post_id,
                )

        except httpx.RequestError as e:
            logger.error("FacebookPublisher: Error de red: %s", e)
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error_message=f"Network error: {str(e)}",
            )
