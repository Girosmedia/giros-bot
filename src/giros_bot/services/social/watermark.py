import base64
import io
import os
import logging
import cairosvg
from PIL import Image

logger = logging.getLogger(__name__)

# Ruta al logo SVG para fondo oscuro (logo reducido = texto completo)
_LOGO_SVG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    "image", "logo-svg", "logo_reducido_para_fondo_negro.svg",
)

# Dimensiones de la banda inferior
_BAND_COLOR  = (15, 23, 42)   # #0f172a
_BAND_HEIGHT = 90              # px
_LOGO_PADDING = 28             # margen derecho e interno en la banda


def _render_svg_to_pil(svg_path: str, target_height: int) -> Image.Image:
    """Renderiza un SVG como imagen RGBA PIL con altura fija."""
    png_bytes = cairosvg.svg2png(url=svg_path, output_height=target_height)
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")


def apply_watermark_to_b64(base_image_b64: str) -> str:
    """
    Aplica una banda negra (#0f172a) al pie de la imagen con el logo de
    Giros Media centrado verticalmente y anclado al margen derecho.

    Args:
        base_image_b64: Imagen original codificada en base64.

    Returns:
        Imagen resultante en JPEG (base64). Devuelve el original si hay error.
    """
    try:
        base_img_bytes = base64.b64decode(base_image_b64)
        base_image = Image.open(io.BytesIO(base_img_bytes)).convert("RGBA")
        w, h = base_image.size

        # 1. Construir banda negra del ancho total
        band = Image.new("RGBA", (w, _BAND_HEIGHT), (*_BAND_COLOR, 255))

        # 2. Renderizar logo SVG — alto = banda − 2×padding
        logo_h = _BAND_HEIGHT - _LOGO_PADDING * 2
        if not os.path.exists(_LOGO_SVG_PATH):
            logger.warning("Logo SVG no encontrado: %s. Saltando watermark.", _LOGO_SVG_PATH)
            return base_image_b64

        logo = _render_svg_to_pil(_LOGO_SVG_PATH, logo_h)

        # 3. Posicionar logo a la derecha de la banda
        lx = w - logo.width - _LOGO_PADDING
        ly = _LOGO_PADDING
        band.paste(logo, (lx, ly), mask=logo)

        # 4. Componer: sobreescribir los últimos _BAND_HEIGHT px de la imagen
        base_image.paste(band, (0, h - _BAND_HEIGHT))

        # 5. Re-codificar a JPEG base64
        output_buffer = io.BytesIO()
        base_image.convert("RGB").save(output_buffer, format="JPEG", quality=90)

        return base64.b64encode(output_buffer.getvalue()).decode("utf-8")

    except Exception as e:
        logger.error("Failed to apply watermark band: %s: %s", type(e).__name__, e, exc_info=True)
        return base_image_b64
