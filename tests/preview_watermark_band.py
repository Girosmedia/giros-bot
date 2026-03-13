"""
Preview script: nueva banda negra de watermark al pie de imagen.

Genera imágenes de prueba con la banda inferior #0f172a y el logotipo
posicionado a la derecha para validación visual ANTES de modificar producción.

Uso:
    .venv/bin/python tests/preview_watermark_band.py
    → guarda en tests/output/preview_*.jpg
"""
import os
import io
import cairosvg
from PIL import Image, ImageDraw

# ── Rutas base ──────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_SVG_DIR = os.path.join(ROOT, "image", "logo-svg")
OUTPUT_DIR = os.path.join(ROOT, "tests", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BAND_COLOR    = (15, 23, 42)      # #0f172a
BAND_HEIGHT   = 90                # px — ajustable
LOGO_PADDING  = 28                # margen derecho e inferior dentro de la banda


def load_svg_as_pil(svg_path: str, target_height: int) -> Image.Image:
    """Renderiza un SVG a RGBA PIL Image con altura fija."""
    png_bytes = cairosvg.svg2png(
        url=svg_path,
        output_height=target_height,
    )
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")


def create_dummy_photo(size=(1200, 1200)) -> Image.Image:
    """Genera una imagen de prueba que simula una foto generada por IA."""
    img = Image.new("RGB", size, (40, 60, 90))
    draw = ImageDraw.Draw(img)

    # Degradado simulado con rectángulos
    for i in range(0, size[1], 4):
        shade = int(40 + (i / size[1]) * 60)
        draw.rectangle([(0, i), (size[0], i + 4)], fill=(shade, shade + 20, shade + 50))

    # Texto de referencia
    draw.text((60, 60), "Imagen de prueba — Giros Media Bot", fill=(220, 220, 220))
    draw.text((60, 100), f"{size[0]}×{size[1]}px — RRSS Preview", fill=(160, 160, 160))

    # Rectángulo central a modo de "sujeto"
    cx, cy = size[0] // 2, size[1] // 2
    draw.rectangle(
        [(cx - 200, cy - 200), (cx + 200, cy + 200)],
        outline=(200, 200, 200),
        width=2,
    )
    draw.text((cx - 90, cy - 10), "« sujeto de prueba »", fill=(200, 200, 200))

    return img


def apply_band_watermark(
    base_image: Image.Image,
    logo_svg_path: str,
    band_height: int = BAND_HEIGHT,
    logo_padding: int = LOGO_PADDING,
) -> Image.Image:
    """
    Aplica la banda negra al pie con el logotipo a la derecha.

    La imagen resultante tiene las mismas dimensiones originales:
    la banda reemplaza los últimos `band_height` píxeles del fondo.
    """
    img = base_image.convert("RGBA")
    w, h = img.size

    # 1. Dibujar banda
    band = Image.new("RGBA", (w, band_height), (*BAND_COLOR, 255))

    # 2. Renderizar logo SVG con altura = banda − 2×padding
    logo_render_h = band_height - logo_padding * 2
    logo = load_svg_as_pil(svg_path=logo_svg_path, target_height=logo_render_h)

    # 3. Posicionar logo a la derecha de la banda
    lx = w - logo.width - logo_padding
    ly = logo_padding
    band.paste(logo, (lx, ly), mask=logo)

    # 4. Pegar banda sobre la imagen base (sobreescribe los últimos px)
    img.paste(band, (0, h - band_height))

    return img.convert("RGB")


def save_preview(image: Image.Image, filename: str) -> str:
    path = os.path.join(OUTPUT_DIR, filename)
    image.save(path, format="JPEG", quality=93)
    print(f"  ✓ Guardado → {path}")
    return path


# ── Generación de previews ───────────────────────────────────────────────────

VARIANTS = [
    {
        "label":   "logo_reducido (1200×1200 — Instagram)",
        "svg":     os.path.join(LOGO_SVG_DIR, "logo_reducido_para_fondo_negro.svg"),
        "size":    (1200, 1200),
        "outfile": "preview_band_logo_reducido_square.jpg",
    },
    {
        "label":   "isotipo (1200×1200 — Instagram)",
        "svg":     os.path.join(LOGO_SVG_DIR, "isotipo_para_fondo_negro.svg"),
        "size":    (1200, 1200),
        "outfile": "preview_band_isotipo_square.jpg",
    },
    {
        "label":   "logo_reducido (1200×628 — Facebook/LinkedIn)",
        "svg":     os.path.join(LOGO_SVG_DIR, "logo_reducido_para_fondo_negro.svg"),
        "size":    (1200, 628),
        "outfile": "preview_band_logo_reducido_banner.jpg",
    },
    {
        "label":   "isotipo (1200×628 — Facebook/LinkedIn)",
        "svg":     os.path.join(LOGO_SVG_DIR, "isotipo_para_fondo_negro.svg"),
        "size":    (1200, 628),
        "outfile": "preview_band_isotipo_banner.jpg",
    },
]


if __name__ == "__main__":
    print("Generando previews de la nueva banda de watermark...\n")
    for v in VARIANTS:
        print(f"  → {v['label']}")
        dummy = create_dummy_photo(size=v["size"])
        result = apply_band_watermark(dummy, v["svg"])
        save_preview(result, v["outfile"])

    print(f"\nListo. Revisa las imágenes en: {OUTPUT_DIR}")
