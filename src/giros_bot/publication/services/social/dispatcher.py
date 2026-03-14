import asyncio
import logging
from typing import List

from .base import ISocialPublisher, SocialPayload, PublishResult
from .make_publisher import MakePublisher
from .facebook import FacebookPublisher
from .instagram import InstagramPublisher
from .linkedin import LinkedInPublisher

logger = logging.getLogger(__name__)

class SocialDispatcher:
    """
    Orquestador que decide a qué conectores enviar el payload.
    Permite ejecutar múltiples publicadores en paralelo.
    """

    def __init__(self):
        # Registramos los conectores activos.
        # Make.com está deprecado a favor de los conectores nativos.
        self.publishers: List[ISocialPublisher] = [
            # MakePublisher(),
            FacebookPublisher(),
            InstagramPublisher(),
            LinkedInPublisher()
        ]

    async def publish_all(self, payload: SocialPayload) -> List[PublishResult]:
        """
        Ejecuta todos los publicadores registrados en paralelo.
        """
        if not self.publishers:
            logger.warning("SocialDispatcher: No hay publicadores registrados.")
            return []

        logger.info("SocialDispatcher: Iniciando publicación en %d plataformas...", len(self.publishers))
        
        # Ejecutar todos los conectores concurrentemente
        tasks = [publisher.publish(payload) for publisher in self.publishers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = []
        for publisher, result in zip(self.publishers, results):
            if isinstance(result, Exception):
                logger.error("SocialDispatcher: Excepción no manejada en %s: %s", publisher.platform_name, result)
                final_results.append(
                    PublishResult(
                        platform=publisher.platform_name,
                        success=False,
                        error_message=f"Unhandled exception: {str(result)}"
                    )
                )
            else:
                final_results.append(result)

        # Resumen de logs
        exitosos = sum(1 for r in final_results if r.success)
        logger.info("SocialDispatcher: Publicación completada. Éxitos: %d/%d", exitosos, len(self.publishers))
        
        return final_results

# Instancia global (Singleton) para ser usada por los nodos
social_dispatcher = SocialDispatcher()
