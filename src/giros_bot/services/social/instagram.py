import logging
import httpx
import asyncio

from giros_bot.config import settings
from .base import ISocialPublisher, SocialPayload, PublishResult

logger = logging.getLogger(__name__)

class InstagramPublisher(ISocialPublisher):
    """
    Conector nativo para publicar en Instagram Business usando Graph API.
    Requiere un flujo de 2 pasos: Crear contenedor de media -> Publicar contenedor.
    """

    @property
    def platform_name(self) -> str:
        return "instagram"

    async def publish(self, payload: SocialPayload) -> PublishResult:
        if not settings.meta_access_token or not settings.instagram_account_id:
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error_message="Credenciales de Meta (Instagram) no configuradas."
            )

        base_url = f"https://graph.facebook.com/v21.0/{settings.instagram_account_id}"
        
        # Instagram no permite links clickeables en el caption, pero lo agregamos igual
        caption = f"{payload.social_assets.instagram_copy}\n\nLink en la bio o visita: {payload.post_url}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # PASO 1: Crear el contenedor de Media
                logger.info("InstagramPublisher: Creando contenedor de media...")
                media_data = {
                    "image_url": payload.image_url,
                    "caption": caption,
                    "access_token": settings.meta_access_token
                }
                
                media_response = await client.post(f"{base_url}/media", data=media_data)
                media_json = media_response.json()
                
                if media_response.status_code != 200:
                    error_msg = media_json.get("error", {}).get("message", "Error desconocido")
                    logger.error("InstagramPublisher: Error creando media: %s", error_msg)
                    return PublishResult(
                        platform=self.platform_name,
                        success=False,
                        error_message=f"Media creation failed: {error_msg}"
                    )
                
                creation_id = media_json.get("id")
                logger.info("InstagramPublisher: Contenedor creado (ID: %s). Esperando procesamiento...", creation_id)
                
                # Pequeña pausa para que Meta procese la imagen antes de publicar
                await asyncio.sleep(3)

                # PASO 2: Publicar el contenedor
                logger.info("InstagramPublisher: Publicando contenedor...")
                publish_data = {
                    "creation_id": creation_id,
                    "access_token": settings.meta_access_token
                }
                
                publish_response = await client.post(f"{base_url}/media_publish", data=publish_data)
                publish_json = publish_response.json()
                
                if publish_response.status_code != 200:
                    error_msg = publish_json.get("error", {}).get("message", "Error desconocido")
                    logger.error("InstagramPublisher: Error publicando media: %s", error_msg)
                    return PublishResult(
                        platform=self.platform_name,
                        success=False,
                        error_message=f"Media publish failed: {error_msg}"
                    )

                post_id = publish_json.get("id")
                logger.info("InstagramPublisher: Publicado con éxito. Post ID: %s", post_id)
                
                return PublishResult(
                    platform=self.platform_name,
                    success=True,
                    post_id=post_id
                )

        except httpx.RequestError as e:
            logger.error("InstagramPublisher: Error de red: %s", e)
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error_message=f"Network error: {str(e)}"
            )
