# Servicio de predicción QSRR-Predict.
# Contexto de construcción: proyecto_final/
#   docker build -f api/Dockerfile -t qsrr-api .
# El modelo NO va dentro de la imagen: se carga al arrancar desde
# models:/qsrr-predict-modelo@champion. Cambiar de versión (promoción o
# rollback) solo mueve el alias; la imagen no se reconstruye.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODELO_URI=models:/qsrr-predict-modelo@champion \
    LINEA_BASE_PATH=/app/linea_base.json \
    REGISTROS_DIR=/app/registros

WORKDIR /app

# libxrender/libxext: dependencias de RDKit en imágenes slim.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libxrender1 libxext6 curl \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt api/requirements.txt
RUN pip install -r api/requirements.txt

# La preparación se importa de src/ (no se copia ni se reimplementa).
COPY src/ src/
COPY api/ api/
# Línea base del PSet 3 empaquetada: respaldo si MLflow no responde.
COPY tests/fixtures/linea_base.json /app/linea_base.json

RUN useradd --create-home --uid 1000 servicio \
    && mkdir -p /app/registros && chown -R servicio /app/registros
USER servicio

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -fsS http://localhost:8000/salud || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
