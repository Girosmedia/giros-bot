import os
import sys

# Add src to python path for proper imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from giros_bot.services.history_db import init_db, save_publication, get_history_context_text, get_visual_history_context_text

print("--- INITIALIZING DB ---")
init_db()

print("\n--- SAVING DUMMY PUBLICATIONS ---")
save_publication({
    "target_date": "2024-03-01",
    "slug": "post-prueba-1",
    "category": "Marketing Digital",
    "topic": "Como usar Instagram",
    "format": "guide",
    "image_prompt": "A modern 3D render of an instagram logo",
    "image_alt": "Logo de instagram en 3D"
})

save_publication({
    "target_date": "2024-03-02",
    "slug": "post-prueba-2",
    "category": "SEO Local",
    "topic": "Posicionar en Google Maps",
    "format": "tips",
    "image_prompt": "A giant Google Maps pin hovering over a store",
    "image_alt": "Pin de Google maps sobre una tienda"
})

print("\n--- FETCHING SCOUT/STRATEGIST CONTEXT ---")
print(get_history_context_text())


print("\n--- FETCHING VISUAL CONTEXT ---")
print(get_visual_history_context_text())

print("\n--- DONE ---")
