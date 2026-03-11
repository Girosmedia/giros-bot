import os
import re
import sys
from glob import glob

# Add src to python path for proper imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from giros_bot.services.history_db import init_db, save_publication

MDX_DIR = "/home/girosmedia/Desarrollos/girosmedia-web-new/content/blog"

def extract_frontmatter_field(content: str, field: str) -> str:
    match = re.search(rf'^{field}:\s*"(.*?)"', content, re.MULTILINE)
    if match:
        return match.group(1)
    match = re.search(rf"^{field}:\s*'(.*?)'", content, re.MULTILINE)
    if match:
        return match.group(1)
    match = re.search(rf"^{field}:\s*(.*?)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""

def main():
    print("--- INICIALIZANDO DB ---")
    init_db()
    
    mdx_files = glob(os.path.join(MDX_DIR, "*.mdx"))
    print(f"Encontrados {len(mdx_files)} archivos MDX para migrar...")
    
    count = 0
    for file_path in mdx_files:
        filename = os.path.basename(file_path)
        slug = filename.replace(".mdx", "")
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Extract basic frontmatter block
        frontmatter_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not frontmatter_match:
            print(f"Skipping {filename}: No frontmatter found.")
            continue
            
        fm = frontmatter_match.group(1)
        
        target_date = extract_frontmatter_field(fm, "date")
        category = extract_frontmatter_field(fm, "category")
        topic = extract_frontmatter_field(fm, "title")
        image_alt = extract_frontmatter_field(fm, "imageAlt")
        visual_brief = extract_frontmatter_field(fm, "visualBrief")
        
        # Fallbacks
        if not target_date:
            target_date = "2024-01-01"
        if not category:
            category = "Marketing Digital"
        if not topic:
            topic = slug
            
        image_prompt = visual_brief if visual_brief else image_alt
        
        save_publication({
            "target_date": target_date,
            "slug": slug,
            "category": category,
            "topic": topic,
            "format": "tips",  # Default format since we don't have it in the frontmatter
            "image_prompt": image_prompt,
            "image_alt": image_alt
        })
        count += 1
        print(f"✓ Migrado: {slug}")
        
    print(f"\n--- MIGRACIÓN COMPLETADA: {count} posts guardados en la base de datos ---")

if __name__ == "__main__":
    main()
