#!/usr/bin/env bash
# Servidor de seguimiento de MLflow del curso (Semana 11 en adelante).
# Se levanta solo cada vez que inicia el Codespace (postStartCommand). Si se cae,
# o si lo detuviste, vuelve a levantarlo con: bash .devcontainer/mlflow-server.sh
#
# Es el mismo patron de un equipo de datos: un servidor guarda el registro de
# todas las corridas, y el codigo solo conoce su direccion por la variable de
# entorno MLFLOW_TRACKING_URI (definida en devcontainer.json). Ningun notebook
# escribe la direccion a mano.
#
#   Corridas, parametros, metricas y etiquetas -> .mlflow/mlflow.db (SQLite)
#   Artefactos (los modelos guardados)          -> .mlflow/artefactos/
#
# .mlflow/ esta en la raiz del repositorio para que sobreviva a "Rebuild
# Container" (lo que vive fuera de /workspaces se pierde al reconstruir), y
# esta en .gitignore: el registro no se sube a git.
set -euo pipefail

# 5050 y no 5000 (el puerto de los ejemplos de MLflow): en macOS el 5000 lo ocupa
# el Receptor AirPlay, y con Dev Containers en local localhost:5000 respondia 403.
PUERTO=5050
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATOS="$RAIZ/.mlflow"
URL="http://127.0.0.1:$PUERTO"

if curl -fsS "$URL/health" >/dev/null 2>&1; then
  echo "MLflow ya esta corriendo en $URL"
  exit 0
fi

mkdir -p "$DATOS/artefactos"

# setsid + nohup: el servidor sigue vivo cuando termina este script.
# Un solo worker alcanza para una persona y ahorra memoria en la maquina de 2 nucleos.
setsid nohup python -m mlflow server \
  --host 127.0.0.1 \
  --port "$PUERTO" \
  --workers 1 \
  --backend-store-uri "sqlite:///$DATOS/mlflow.db" \
  --artifacts-destination "$DATOS/artefactos" \
  >"$DATOS/servidor.log" 2>&1 </dev/null &

# La primera vez crea las tablas de la base de datos y tarda unos segundos mas.
for _ in $(seq 1 60); do
  if curl -fsS "$URL/health" >/dev/null 2>&1; then
    echo "MLflow listo en $URL (interfaz en la pestana Ports, puerto $PUERTO)"
    exit 0
  fi
  sleep 1
done

echo "MLflow no respondio en 60 segundos. Ultimas lineas de $DATOS/servidor.log:" >&2
tail -n 20 "$DATOS/servidor.log" >&2 || true
exit 1
