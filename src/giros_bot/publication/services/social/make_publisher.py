import logging
import httpx

from giros_bot.config import settings
from .base import ISocialPublisher, SocialPayload, PublishResult

logger = logging.getLogger(__name__)

class MakePublisher(ISocialPublisher):
    """
    Conector Legacy que envía el payload a Make.com vía Webhook.
    Make.com se encarga de distribuir a LinkedIn, Facebook e Instagram.
    """

    @property
    def platform_name(self) -> str:
        return "make_webhook"

    async def publish(self, payload: SocialPayload) -> PublishResult:
        if not settings.social_webhook_url:
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error_message="SOCIAL_WEBHOOK_URL no está configurado."
            )

        # El payload exacto que Make.com espera actualmente
        make_payload = {
            "social_assets": payload.social_assets.model_dump(),
            "image_url": payload.image_url,
            "post_url": payload.post_url,
            "image_prompt": payload.image_prompt,
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(settings.social_webhook_url, json=make_payload)
                response.raise_for_status()
                logger.info("MakePublisher: Webhook disparado con éxito. Status: %d", response.status_code)
                
                return PublishResult(
                    platform=self.platform_name,
                    success=True,
                    post_id="make_dispatched"
                )
        except httpx.HTTPError as e:
            logger.error("MakePublisher: Falló el webhook de Make.com: %s", e)
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error_message=str(e)
            )
