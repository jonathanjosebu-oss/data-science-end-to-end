# Imagen de las tareas Python de Kestra (produccion_lotes, monitoreo,
# reentrenamiento). El código llega como archivos de namespace (src/,
# monitoreo/, scripts/); la imagen solo fija las dependencias.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
