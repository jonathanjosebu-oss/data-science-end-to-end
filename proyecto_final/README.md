# QSRR-Predict — Proyecto final

Predicción del tiempo de retención cromatográfica (columnas C18) a partir de la
estructura molecular y las condiciones del método, con datos públicos de
RepoRT. Este directorio reúne los PSets 1–4 en un solo proyecto reproducible.
Los cambios respecto a las entregas anteriores están en
[`docs/cambios.md`](docs/cambios.md).

> Estado: en construcción (PSet 4). Las secciones marcadas ⏳ aún no existen.

## 0. Requisitos y configuración

- Docker con Compose y unos 10 GB libres en disco.
- Una cuenta de Snowflake con un rol que pueda crear esquemas, tablas, stages y
  formatos de archivo en la base indicada.
- Python 3.11 para los notebooks y las pruebas locales.

```bash
cp .env.example .env      # completa Snowflake y las credenciales de Kestra
docker compose up -d --build
docker compose logs kestra-deploy   # debe terminar con "Despliegue completo."
```

| Servicio | Puerto | Función |
|---|---|---|
| `kestra` | 8080 | Orquestación (usuario y contraseña de `.env`). |
| `kestra-deploy` | — | Valida e importa los flows de `kestra/` y sus archivos al arrancar. |
| `spark` | — | Construye la OBT (imagen `qsrr-spark` con el conector de Snowflake). |
| `dbt-image` / `dbt` | — | Imagen `qsrr-dbt`; Kestra la lanza en cada ejecución. |
| `mlflow` | 5000 | Tracking y Model Registry. |
| `api`, tablero | — | ⏳ |

Para cambiar código de los flows, dbt o Spark: `docker compose run --rm kestra-deploy`.

## 1. Fuente → Raw → Bronze → Silver → Gold → OBT

En Kestra (namespace `qsrr.proyecto`) ejecuta el flow **`ingesta`**. Hace todo
el recorrido en una sola ejecución:

1. Resuelve el commit de RepoRT vigente en la fecha lógica y descarga los TSV
   canónicos (`kestra/scripts/ingest_repo_rt.py`).
2. Publica la partición `SNAPSHOT_DATE` en `RAW.RAW_REPORT_DATA`, con
   `SOURCE_COMMIT` como linaje.
3. `dbt build`: Bronze, Silver (reglas de limpieza auditables) y Gold (esquema
   estrella), con 44 pruebas.
4. Spark valida las dimensiones y escribe `GOLD.OBT_QSRR_FINAL`.

Para el histórico, usa el flow **`backfill`** con `start_date`, `end_date` y
`step`. El detalle de las reglas de limpieza y las pruebas está en
[`dbt/`](dbt/) y en `docs/cambios.md` (PSet 2).

## 2. EDA y modelo ⏳

Los notebooks `01`–`05` vienen del PSet 3 y se volverán a ejecutar con la OBT
corregida (ver *Decisiones actualizadas* en `docs/cambios.md`).

## 3. Registro → API → simulación → monitoreo → reentrenamiento ⏳

## Pruebas

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/
```
