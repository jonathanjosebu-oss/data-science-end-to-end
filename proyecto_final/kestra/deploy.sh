#!/bin/sh
# Importa en Kestra los flows de kestra/*.yml y los archivos de namespace
# que usan (script de ingesta, proyecto dbt y job Spark). Idempotente: se puede
# ejecutar cada vez que cambie el código. Lo lanza el servicio kestra-deploy.
set -eu

KESTRA_URL="${KESTRA_URL:-http://kestra:8080}"
NAMESPACE="${NAMESPACE:-qsrr.proyecto}"
SRC="${SRC:-/opt/proyecto}"
AUTH="${KESTRA_USER}:${KESTRA_PASSWORD}"
API="${KESTRA_URL}/api/v1/main"

echo "Esperando a Kestra en ${KESTRA_URL}..."
i=0
until curl -fsS -u "$AUTH" -o /dev/null "${API}/flows/search?size=1"; do
  i=$((i + 1))
  [ "$i" -ge 60 ] && { echo "Kestra no respondió en 5 minutos" >&2; exit 1; }
  sleep 5
done

upload_file() {  # $1 = ruta local, $2 = ruta en el namespace
  curl -fsS -u "$AUTH" -o /dev/null -X POST \
    "${API}/namespaces/${NAMESPACE}/files?path=/$2" \
    -F "fileContent=@$1"
  echo "  archivo de namespace /$2"
}

echo "Subiendo archivos de namespace a ${NAMESPACE}:"
upload_file "${SRC}/kestra/scripts/ingest_repo_rt.py" ingest_repo_rt.py
upload_file "${SRC}/spark/obt_processing.py" spark/obt_processing.py
cd "${SRC}"
find dbt/dbt_project.yml dbt/models dbt/macros dbt/tests -type f \
  \( -name '*.sql' -o -name '*.yml' \) | sort | while read -r f; do
  upload_file "$f" "$f"
done

echo "Validando flows:"
for flow in "${SRC}"/kestra/*.yml; do
  result=$(curl -fsS -u "$AUTH" -X POST "${API}/flows/validate" \
    -H "Content-Type: application/x-yaml" --data-binary "@${flow}")
  if echo "$result" | grep -q '"constraints"'; then
    echo "Flow inválido: $(basename "$flow"): $result" >&2
    exit 1
  fi
  echo "  $(basename "$flow") OK"
done

echo "Importando flows:"
for flow in "${SRC}"/kestra/*.yml; do
  curl -fsS -u "$AUTH" -o /dev/null -X POST "${API}/flows/import" \
    -F "fileUpload=@${flow}"
  echo "  $(basename "$flow")"
done
echo "Despliegue completo."
