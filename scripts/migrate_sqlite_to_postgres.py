"""
Migración one-shot: SQLite → PostgreSQL

Lee todos los registros de data/publications.db y los inserta en la BD
PostgreSQL definida en DATABASE_URL. Es seguro de re-ejecutar: los slugs
duplicados se ignoran (ON CONFLICT DO NOTHING sobre el slug).

Uso:
    cd /home/girosmedia/Desarrollos/Giros-bot
    python scripts/migrate_sqlite_to_postgres.py
"""

import asyncio
import logging
import sqlite3
import sys
from pathlib import Path

# Añadir src/ al path para importar config y modelos
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from giros_bot.config import settings
from giros_bot.services.history_db import Base, Publication

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SQLITE_PATH = ROOT / "data" / "publications.db"


def read_sqlite_records() -> list[dict]:
    """Lee todos los registros desde la BD SQLite existente."""
    if not SQLITE_PATH.exists():
        logger.warning("No se encontró SQLite en %s. Nada que migrar.", SQLITE_PATH)
        return []

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT target_date, slug, category, topic, format,
               COALESCE(visual_style, '') AS visual_style,
               image_prompt, image_alt
        FROM publications
        ORDER BY id ASC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    logger.info("SQLite: %d registros encontrados.", len(rows))
    return rows


async def migrate(records: list[dict]) -> None:
    """Inserta los registros en PostgreSQL ignorando duplicados por slug."""
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Garantizar que la tabla existe
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    inserted = 0
    skipped = 0

    async with session_factory() as session:
        for row in records:
            # Verificar si el slug ya existe para hacer la operación idempotente
            existing = await session.execute(
                text("SELECT id FROM publications WHERE slug = :slug"),
                {"slug": row["slug"]},
            )
            if existing.scalar_one_or_none() is not None:
                logger.debug("Slug '%s' ya existe en PostgreSQL, se omite.", row["slug"])
                skipped += 1
                continue

            session.add(Publication(
                target_date=  row["target_date"],
                slug=         row["slug"],
                category=     row["category"],
                topic=        row["topic"],
                format=       row["format"],
                visual_style= row["visual_style"],
                image_prompt= row["image_prompt"],
                image_alt=    row["image_alt"],
            ))
            inserted += 1

        await session.commit()

    await engine.dispose()

    logger.info("─────────────────────────────────────────")
    logger.info("Migración completada.")
    logger.info("  Insertados : %d", inserted)
    logger.info("  Omitidos   : %d (ya existían)", skipped)
    logger.info("  Total SQLite: %d", len(records))
    logger.info("─────────────────────────────────────────")


async def main() -> None:
    records = read_sqlite_records()
    if not records:
        logger.info("No hay registros que migrar. Saliendo.")
        return
    await migrate(records)


if __name__ == "__main__":
    asyncio.run(main())
