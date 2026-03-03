import logging
import httpx
import base64
import os
import re

from giros_bot.config import settings
from .base import ISocialPublisher, SocialPayload, PublishResult

logger = logging.getLogger(__name__)

class LinkedInPublisher(ISocialPublisher):
    """
    Conector nativo para publicar en LinkedIn usando la API v2 (UGC Posts).
    Incluye lógica de auto-refresh del token si este expira (HTTP 401).
    """

    @property
    def platform_name(self) -> str:
        return "linkedin"

    async def _refresh_token(self, client: httpx.AsyncClient) -> str | None:
        """
        Intenta obtener un nuevo access token usando el refresh token.
        Si tiene éxito, actualiza el archivo .env y retorna el nuevo token.
        """
        if not settings.linkedin_refresh_access_token or not settings.linkedin_client_id or not settings.linkedin_client_secret:
            logger.error("LinkedInPublisher: Faltan credenciales para hacer refresh del token.")
            return None

        logger.info("LinkedInPublisher: Intentando refrescar el Access Token...")
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": settings.linkedin_refresh_access_token,
            "client_id": settings.linkedin_client_id,
            "client_secret": settings.linkedin_client_secret
        }

        try:
            resp = await client.post(
                "https://www.linkedin.com/oauth/v2/accessToken",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if resp.status_code != 200:
                logger.error("LinkedInPublisher: Falló el refresh del token: %s", resp.text)
                return None
                
            new_token = resp.json().get("access_token")
            if new_token:
                logger.info("LinkedInPublisher: Token refrescado con éxito. Actualizando .env...")
                self._update_env_file("LINKEDIN_ACCESS_TOKEN", new_token)
                # Actualizar en memoria para la ejecución actual
                settings.linkedin_access_token = new_token
                return new_token
                
        except Exception as e:
            logger.error("LinkedInPublisher: Excepción durante el refresh del token: %s", e)
            
        return None

    def _update_env_file(self, key: str, new_value: str):
        """Actualiza una variable en el archivo .env de forma segura."""
        env_path = ".env"
        if not os.path.exists(env_path):
            logger.warning("LinkedInPublisher: Archivo .env no encontrado, no se puede guardar el nuevo token.")
            return

        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            updated = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    # Mantener comillas si las tenía
                    if line.strip().endswith('"') and line.split("=")[1].startswith('"'):
                        lines[i] = f'{key}="{new_value}"\n'
                    else:
                        lines[i] = f'{key}={new_value}\n'
                    updated = True
                    break

            if not updated:
                lines.append(f'\n{key}="{new_value}"\n')

            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
                
        except Exception as e:
            logger.error("LinkedInPublisher: Error escribiendo en .env: %s", e)

    async def publish(self, payload: SocialPayload, is_retry: bool = False) -> PublishResult:
        if not settings.linkedin_access_token or not settings.linkedin_author_urn:
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error_message="Credenciales de LinkedIn no configuradas."
            )

        headers = {
            "Authorization": f"Bearer {settings.linkedin_access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                asset_urn = None

                # Si hay imagen, ejecutamos el flujo de subida de 2 pasos
                if payload.image_bytes_b64:
                    logger.info("LinkedInPublisher: Iniciando subida de imagen...")
                    
                    # PASO 1: Registrar el upload
                    register_payload = {
                        "registerUploadRequest": {
                            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                            "owner": settings.linkedin_author_urn,
                            "serviceRelationships": [
                                {
                                    "relationshipType": "OWNER",
                                    "identifier": "urn:li:userGeneratedContent"
                                }
                            ]
                        }
                    }
                    
                    reg_resp = await client.post(
                        "https://api.linkedin.com/v2/assets?action=registerUpload",
                        json=register_payload,
                        headers=headers
                    )
                    
                    # Lógica de Auto-Refresh si el token expiró (HTTP 401)
                    if reg_resp.status_code == 401 and not is_retry:
                        logger.warning("LinkedInPublisher: Token expirado (401). Iniciando flujo de refresh...")
                        new_token = await self._refresh_token(client)
                        if new_token:
                            # Reintentar la publicación completa con el nuevo token
                            return await self.publish(payload, is_retry=True)
                        else:
                            return PublishResult(
                                platform=self.platform_name,
                                success=False,
                                error_message="Token expirado y falló el auto-refresh."
                            )
                    
                    if reg_resp.status_code != 200:
                        logger.error("LinkedInPublisher: Error registrando upload: %s", reg_resp.text)
                        return PublishResult(
                            platform=self.platform_name,
                            success=False,
                            error_message=f"Register upload failed: {reg_resp.text}"
                        )
                        
                    reg_data = reg_resp.json()
                    upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                    asset_urn = reg_data["value"]["asset"]

                    # PASO 2: Subir los bytes de la imagen
                    logger.info("LinkedInPublisher: Subiendo bytes de la imagen a %s", upload_url)
                    img_bytes = base64.b64decode(payload.image_bytes_b64)
                    
                    # Para la subida binaria, el Content-Type debe ser el de la imagen, no JSON
                    upload_headers = headers.copy()
                    upload_headers["Content-Type"] = "image/jpeg"
                    
                    upload_resp = await client.put(
                        upload_url,
                        content=img_bytes,
                        headers=upload_headers
                    )
                    
                    if upload_resp.status_code not in (200, 201):
                        logger.error("LinkedInPublisher: Error subiendo imagen: %s", upload_resp.text)
                        return PublishResult(
                            platform=self.platform_name,
                            success=False,
                            error_message=f"Image upload failed: {upload_resp.text}"
                        )
                        
                    logger.info("LinkedInPublisher: Imagen subida con éxito. Asset URN: %s", asset_urn)

                # PASO 3: Crear el post (UGC Post)
                logger.info("LinkedInPublisher: Creando el post...")
                
                # Construir el texto del post
                text_content = f"{payload.social_assets.linkedin_copy}\n\nLee el artículo completo aquí: {payload.post_url}"
                
                post_payload = {
                    "author": settings.linkedin_author_urn,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {
                                "text": text_content
                            },
                            "shareMediaCategory": "NONE"
                        }
                    },
                    "visibility": {
                        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                    }
                }

                # Si logramos subir la imagen, la adjuntamos al post
                if asset_urn:
                    post_payload["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
                    post_payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                        {
                            "status": "READY",
                            "description": {
                                "text": payload.image_prompt or "Imagen generada por IA"
                            },
                            "media": asset_urn,
                            "title": {
                                "text": "Imagen del artículo"
                            }
                        }
                    ]

                post_resp = await client.post(
                    "https://api.linkedin.com/v2/ugcPosts",
                    json=post_payload,
                    headers=headers
                )

                # Lógica de Auto-Refresh si el token expiró (HTTP 401) y no había imagen
                if post_resp.status_code == 401 and not is_retry:
                    logger.warning("LinkedInPublisher: Token expirado (401) al crear post. Iniciando flujo de refresh...")
                    new_token = await self._refresh_token(client)
                    if new_token:
                        return await self.publish(payload, is_retry=True)
                    else:
                        return PublishResult(
                            platform=self.platform_name,
                            success=False,
                            error_message="Token expirado y falló el auto-refresh."
                        )

                if post_resp.status_code != 201:
                    logger.error("LinkedInPublisher: Error creando post: %s", post_resp.text)
                    return PublishResult(
                        platform=self.platform_name,
                        success=False,
                        error_message=f"Post creation failed: {post_resp.text}"
                    )

                post_id = post_resp.json().get("id")
                logger.info("LinkedInPublisher: Publicado con éxito. Post ID: %s", post_id)
                
                return PublishResult(
                    platform=self.platform_name,
                    success=True,
                    post_id=post_id
                )

        except httpx.RequestError as e:
            logger.error("LinkedInPublisher: Error de red: %s", e)
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error_message=f"Network error: {str(e)}"
            )
