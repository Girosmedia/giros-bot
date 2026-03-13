FROM python:3.12-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Instalar uv
RUN pip install --no-cache-dir uv

# Copiar solo los archivos de dependencias primero (mejor cache)
# README.md es requerido por hatchling para construir el paquete
COPY pyproject.toml uv.lock README.md ./

# Instalar dependencias en el venv
RUN uv sync --no-dev --frozen

# Copiar el resto del código
COPY . .

# Directorio de datos persistente
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.giros_bot.main:app", "--host", "0.0.0.0", "--port", "8000"]
