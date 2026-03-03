import asyncio
import sys
import os
from datetime import date

# Agregar 'src' al path para que 'giros_bot' sea importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

# Ahora importamos lo necesario del archivo de tests
from tests.test_pipeline_dry_run import main

if __name__ == "__main__":
    # Seteamos el sys.argv si queremos pasar una fecha, o dejamos que tome la de hoy
    asyncio.run(main())
