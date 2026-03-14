import asyncio
import logging
import sys
from pathlib import Path

# Añadir el directorio src al path para poder importar los módulos
sys.path.append(str(Path(__file__).parent.parent / "src"))

from giros_bot.publication.services.social.base import SocialPayload
from giros_bot.schemas.state import SocialAssets
from giros_bot.publication.services.social.facebook import FacebookPublisher
from giros_bot.publication.services.social.instagram import InstagramPublisher
from giros_bot.publication.services.social.linkedin import LinkedInPublisher

# Configurar logging para ver los resultados en consola
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

async def test_social_publishers():
    print("--- INICIANDO PRUEBA DE CONECTORES SOCIALES ---")
    
    # Crear un payload de prueba
    # Usamos una imagen pública real de tu blog para que Meta pueda descargarla
    test_payload = SocialPayload(
        social_assets=SocialAssets(
            facebook_copy="🤖 [TEST AUTOMÁTICO] Probando la nueva integración nativa de Facebook Graph API para Giros Media.",
            instagram_copy="🤖 [TEST AUTOMÁTICO] Probando la nueva integración nativa de Instagram Graph API para Giros Media.",
            linkedin_copy="🤖 [TEST AUTOMÁTICO] Probando la nueva integración nativa de LinkedIn API v2 para Giros Media.",
            short_url="https://girosmedia.cl"
        ),
        image_url="https://images.unsplash.com/photo-1516321318423-f06f85e504b3?q=80&w=1000&auto=format&fit=crop",
        post_url="https://girosmedia.cl",
        image_prompt="Test prompt",
        image_bytes_b64=None # No lo necesitamos para Meta, ellos descargan la URL
    )

    # Probar Facebook
    print("\n--- PROBANDO FACEBOOK ---")
    fb = FacebookPublisher()
    fb_result = await fb.publish(test_payload)
    print(f"Resultado Facebook: {fb_result.model_dump()}")

    # Probar Instagram
    print("\n--- PROBANDO INSTAGRAM ---")
    ig = InstagramPublisher()
    ig_result = await ig.publish(test_payload)
    print(f"Resultado Instagram: {ig_result.model_dump()}")

    # Probar LinkedIn
    print("\n--- PROBANDO LINKEDIN ---")
    li = LinkedInPublisher()
    li_result = await li.publish(test_payload)
    print(f"Resultado LinkedIn: {li_result.model_dump()}")

if __name__ == "__main__":
    asyncio.run(test_social_publishers())
