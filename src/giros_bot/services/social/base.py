from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel

from ...schemas.state import SocialAssets

class SocialPayload(BaseModel):
    """Datos necesarios para publicar en cualquier red social."""
    social_assets: SocialAssets
    image_url: str
    post_url: str
    image_prompt: Optional[str] = None
    image_bytes_b64: Optional[str] = None

class PublishResult(BaseModel):
    """Resultado de un intento de publicación."""
    platform: str
    success: bool
    post_id: Optional[str] = None
    error_message: Optional[str] = None

class ISocialPublisher(ABC):
    """Interfaz base para todos los conectores de redes sociales."""
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Nombre de la plataforma (ej: 'linkedin', 'make', 'facebook')."""
        pass

    @abstractmethod
    async def publish(self, payload: SocialPayload) -> PublishResult:
        """Ejecuta la publicación en la red social correspondiente."""
        pass
