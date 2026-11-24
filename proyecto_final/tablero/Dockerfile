# Tablero de monitoreo (PSet 4 §6.4). Contexto de construcción: proyecto_final/
#   docker build -f tablero/Dockerfile -t qsrr-tablero .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY tablero/requirements.txt tablero/requirements.txt
RUN pip install -r tablero/requirements.txt
# Solo el acceso a Snowflake (src/almacen.py usa src/datos.py).
COPY src/__init__.py src/datos.py src/almacen.py src/
COPY tablero/app.py tablero/app.py

RUN useradd --create-home --uid 1000 tablero
USER tablero
EXPOSE 8501
CMD ["streamlit", "run", "tablero/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
