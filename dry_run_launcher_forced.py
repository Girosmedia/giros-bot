import asyncio
import sys
import os
from datetime import date

# Agregar 'src' al path para que 'giros_bot' sea importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from giros_bot.schemas.state import FrontendCategory
from tests.test_pipeline_dry_run import run_dry_pipeline, print_report
import time

async def main():
    target = date.today().isoformat()
    print(f"
🚀 Iniciando DRY RUN FORZADO (SEO Local) para {target}...")
    
    # Mockeamos el estado inicial para forzar la categoría
    # Esto obligará al Strategist a trabajar en este tema
    
    start = time.time()
    # Ejecutamos el pipeline. Nota: scheduler_node se ejecutará pero 
    # el Strategist recibirá el target_category que le pasemos si modificamos run_dry_pipeline
    # Para hacerlo simple, solo ejecutamos y vemos qué decide el azar O 
    # modificamos el estado inicial en run_dry_pipeline.
    
    # Vamos a usar la función original pero le pasaremos un estado inicial con categoría
    state = await run_dry_pipeline(target)
    
    elapsed = time.time() - start
    print_report(state, elapsed)

if __name__ == "__main__":
    asyncio.run(main())
