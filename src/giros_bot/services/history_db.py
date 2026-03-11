import json
import logging
import sqlite3
from typing import TypedDict
from pathlib import Path

logger = logging.getLogger(__name__)

# Asegurarse que el directorio data existe (al nivel de la raíz o fuera de src)
# En este caso vamos a guardarlo en: /home/girosmedia/Desarrollos/Giros-bot/data
DB_DIR = Path("/home/girosmedia/Desarrollos/Giros-bot/data")
DB_PATH = DB_DIR / "publications.db"

class PublicationRecord(TypedDict):
    target_date: str
    slug: str
    category: str
    topic: str
    format: str
    image_prompt: str
    image_alt: str


def init_db() -> None:
    """Inicializa la base de datos y crea la tabla si no existe."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
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
    conn.close()
    logger.info("Base de datos de historial inicializada en %s", DB_PATH)


def save_publication(data: PublicationRecord) -> None:
    """Guarda un registro de una publicación exitosa."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO publications (target_date, slug, category, topic, format, image_prompt, image_alt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data["target_date"],
            data["slug"],
            data["category"],
            data["topic"],
            data["format"],
            data["image_prompt"],
            data["image_alt"]
        ))
        conn.commit()
        conn.close()
        logger.info("Publicación %s (%s) guardada en DB", data["slug"], data["target_date"])
    except Exception as e:
        logger.error("Error al guardar en DB de historial: %s", e)


def get_recent_history(limit: int = 10) -> list[PublicationRecord]:
    """Obtiene las últimas N publicaciones."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT target_date, slug, category, topic, format, image_prompt, image_alt
            FROM publications
            ORDER BY target_date DESC, id DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]  # Type cast Row to dict
    except Exception as e:
        logger.error("Error al leer de DB de historial: %s", e)
        return []


def get_history_context_text(limit: int = 10) -> str:
    """
    Formatea el historial reciente para inyectarlo en Scout y Strategist.
    Ayuda a evitar repetir títulos y temas.
    """
    history = get_recent_history(limit)
    if not history:
        return "No hay publicaciones recientes registradas aún."
    
    lines = ["## ÚLTIMAS PUBLICACIONES (NO REPETIR)"]
    for i, rep in enumerate(history, start=1):
        lines.append(f"{i}. Fecha: {rep['target_date']} | Tema: {rep['topic']} | Categoría: {rep['category']} | Formato: {rep['format']}")
    
    return "\n".join(lines)


def get_visual_history_context_text(limit: int = 10) -> str:
    """
    Formatea el historial reciente enfocado en lo visual para inyectarlo en el Visual_Agent.
    Ayuda a que el agente visual cambie de estilo, colores o ángulos de composición.
    """
    history = get_recent_history(limit)
    if not history:
        return "No hay publicaciones visuales recientes registradas aún."
    
    lines = ["## ÚLTIMAS IMÁGENES GENERADAS (ALTERNA ESTOS ESTILOS, COLORES Y ÁNGULOS)"]
    for i, rep in enumerate(history, start=1):
        lines.append(f"- Publicación '{rep['topic']}':")
        lines.append(f"  * Prompt usado: {rep['image_prompt']}")
        lines.append(f"  * Descripción visual (Alt): {rep['image_alt']}")
    
    return "\n".join(lines)
