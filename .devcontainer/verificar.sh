#!/usr/bin/env bash
# Verifica que cada herramienta del curso responde. Corre al crear el Codespace y
# puedes repetirla cuando quieras: bash .devcontainer/verificar.sh
set -euo pipefail
# sed -n en vez de head: head cierra la tuberia antes de que el comando termine
# de escribir, y con pipefail eso aborta el script (codigo 141, SIGPIPE).

echo "--- Verificacion del ambiente ---"
python --version
java -version 2>&1 | sed -n '1p'
terraform -version | sed -n '1p'
docker --version
docker compose version
dbt --version | sed -n '1,3p'
python - <<'PY'
import duckdb, kafka, matplotlib, pandas, pyspark, sklearn
print(f"pandas {pandas.__version__} | duckdb {duckdb.__version__} | pyspark {pyspark.__version__}")
print(f"scikit-learn {sklearn.__version__} | matplotlib {matplotlib.__version__} | kafka-python {kafka.__version__}")
PY
jupyter lab --version | sed -n '1s/^/jupyterlab /p'
jupyter kernelspec list | sed -n '/python3/s/^ */kernel de notebooks: /p'
python -m mlflow --version
python -c "import fastapi; print(f'fastapi {fastapi.__version__}')"
pytest --version
# El servidor de MLflow se levanta al iniciar el contenedor, despues de esta
# verificacion: al crear el Codespace es normal que todavia no responda.
if curl -fsS "${MLFLOW_TRACKING_URI:-http://127.0.0.1:5050}/health" >/dev/null 2>&1; then
  echo "servidor de MLflow: responde en ${MLFLOW_TRACKING_URI:-http://127.0.0.1:5050}"
else
  echo "servidor de MLflow: no responde todavia (se levanta solo al iniciar; a mano: bash .devcontainer/mlflow-server.sh)"
fi

echo
echo "Ambiente listo. Si algo de lo anterior fallo, avisame antes de la proxima sesion."
