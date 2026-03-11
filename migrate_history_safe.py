import os
import re
import sqlite3
from glob import glob

DB_PATH = "/home/girosmedia/Desarrollos/Giros-bot/data/publications.db"
MDX_DIR = "/home/girosmedia/Desarrollos/girosmedia-web-new/content/blog"

def extract_field(fm, field):
    match = re.search(rf'^{field}:\s*"(.*?)"', fm, re.MULTILINE)
    if match: return match.group(1)
    match = re.search(rf"^{field}:\s*'(.*?)'", fm, re.MULTILINE)
    if match: return match.group(1)
    match = re.search(rf"^{field}:\s*(.*?)$", fm, re.MULTILINE)
    if match: return match.group(1).strip()
    return ""

def main():
    print("--- INICIALIZANDO MIGRACIÓN ---")
    
    # Connect directly to SQLite
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_date TEXT NOT NULL,
            slug TEXT NOT NULL,
            category TEXT NOT NULL,
            topic TEXT NOT NULL,
            format TEXT NOT NULL,
            image_prompt TEXT NOT NULL,
            image_alt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    
    mdx_files = glob(os.path.join(MDX_DIR, "*.mdx"))
    print(f"Encontrados {len(mdx_files)} archivos MDX para migrar...")
    
    count = 0
    for file_path in mdx_files:
        filename = os.path.basename(file_path)
        slug = filename.replace(".mdx", "")
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        frontmatter_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not frontmatter_match:
            print(f"Skipping {filename}: No frontmatter found.")
            continue
            
        fm = frontmatter_match.group(1)
        
        target_date = extract_field(fm, "date")
        category = extract_field(fm, "category")
        topic = extract_field(fm, "title")
        image_alt = extract_field(fm, "imageAlt")
        visual_brief = extract_field(fm, "visualBrief")
        
        if not target_date: target_date = "2024-01-01"
        if not category: category = "Marketing Digital"
        if not topic: topic = slug
            
        image_prompt = visual_brief if visual_brief else image_alt
        
        cursor.execute('''
            INSERT INTO publications (target_date, slug, category, topic, format, image_prompt, image_alt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (target_date, slug, category, topic, "tips", image_prompt, image_alt))
        count += 1
        
    conn.commit()
    conn.close()
    
    print(f"\n--- MIGRACIÓN COMPLETADA: {count} posts guardados en la base de datos ---")

if __name__ == "__main__":
    main()
