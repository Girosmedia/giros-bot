import os
from PIL import Image, ImageDraw

def create_dummy_image(output_path, size=(1024, 1024), color=(73, 109, 137)):
    img = Image.new('RGB', size, color)
    d = ImageDraw.Draw(img)
    d.text((10,10), 'Dummy Generated Image', fill=(255,255,0))
    img.save(output_path)

def apply_watermark(base_image_path, watermark_path, output_path, padding=40):
    base_image = Image.open(base_image_path).convert('RGBA')
    watermark = Image.open(watermark_path).convert('RGBA')
    
    # Resize watermark: make it 25% of the image width
    max_width = int(base_image.width * 0.25)
    ratio = max_width / watermark.width
    new_size = (max_width, int(watermark.height * ratio))
    watermark = watermark.resize(new_size, Image.Resampling.LANCZOS)
    
    # Calculate position (bottom_right)
    x = base_image.width - watermark.width - padding
    y = base_image.height - watermark.height - padding
    
    # Keep original alpha of watermark
    transparent = Image.new('RGBA', base_image.size, (0,0,0,0))
    transparent.paste(watermark, (x, y), mask=watermark)
    
    # Composite
    watermarked = Image.alpha_composite(base_image, transparent)
    watermarked.convert('RGB').save(output_path)

if __name__ == '__main__':
    dummy_path = 'dummy.jpg'
    output_path = 'dummy_watermarked.jpg'
    watermark_paths = [
        'image/Recurso 4@2ximagoc.png',
        'image/logo-svg/logo.png',
        'image/Recurso 2@2ximagoc.png'
    ]
    
    create_dummy_image(dummy_path)
    print(f'Created dummy image at {dummy_path}')
    
    for w_path in watermark_paths:
        if os.path.exists(w_path):
            out_name = f"watermarked_{os.path.basename(w_path)}.jpg"
            apply_watermark(dummy_path, w_path, out_name)
            print(f'Watermark {w_path} applied. Saved to {out_name}')
        else:
            print(f'Watermark file {w_path} not found.')
