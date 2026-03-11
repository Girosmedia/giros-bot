import base64
import io
import os
import logging
from PIL import Image

logger = logging.getLogger(__name__)

def apply_watermark_to_b64(base_image_b64: str, watermark_filename: str = "Recurso 4@2ximagoc.png") -> str:
    """
    Applies the Giros Media logo as a watermark to a base64 encoded image.
    The watermark is placed at the bottom-right corner, sized to 25% of the image's width.

    Args:
        base_image_b64: Base64 encoded string of the original image.
        watermark_filename: The filename of the logo found in the 'image' or 'image/logo-svg' directory.
    
    Returns:
        Base64 encoded string of the watermarked image in JPEG format, or the original if an error occurs.
    """
    try:
        # Decode base image from base64
        base_img_bytes = base64.b64decode(base_image_b64)
        base_image = Image.open(io.BytesIO(base_img_bytes)).convert("RGBA")

        # Resolve watermark path
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        watermark_path = os.path.join(base_dir, "image", watermark_filename)
        
        if not os.path.exists(watermark_path):
            watermark_path = os.path.join(base_dir, "image", "logo-svg", watermark_filename)

        if not os.path.exists(watermark_path):
            logger.warning(f"Watermark image not found at expected paths for {watermark_filename}. Skipping watermark.")
            return base_image_b64

        watermark = Image.open(watermark_path).convert("RGBA")

        # Resize watermark: make it 25% of the image width
        padding = 40
        max_width = int(base_image.width * 0.25)
        ratio = max_width / watermark.width
        new_size = (max_width, int(watermark.height * ratio))
        watermark = watermark.resize(new_size, Image.Resampling.LANCZOS)

        # Calculate position (bottom_right)
        x = base_image.width - watermark.width - padding
        y = base_image.height - watermark.height - padding

        # Paste keeping original alpha of watermark
        transparent = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        transparent.paste(watermark, (x, y), mask=watermark)

        # Composite base and transparent layer with watermark
        watermarked = Image.alpha_composite(base_image, transparent)

        # Re-encode to base64 jpeg
        output_buffer = io.BytesIO()
        watermarked.convert("RGB").save(output_buffer, format="JPEG", quality=90)
        watermarked_bytes = output_buffer.getvalue()

        return base64.b64encode(watermarked_bytes).decode("utf-8")

    except Exception as e:
        logger.error("Failed to apply watermark: %s: %s", type(e).__name__, e, exc_info=True)
        return base_image_b64
