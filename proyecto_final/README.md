# QSRR-Predict — Proyecto final

Predicción del tiempo de retención cromatográfica (columnas C18) a partir de la
estructura molecular y las condiciones del método, con datos públicos de
RepoRT. Este directorio reúne los PSets 1–4 en un solo proyecto reproducible.
Los cambios respecto a las entregas anteriores están en
[`docs/cambios.md`](docs/cambios.md).

> Estado: PSet 4. Documento técnico y presentación en `docs/`. Video de la
> demostración: <https://www.youtube.com/watch?v=skNClUvKuNw>.

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
| `jobs-image` | — | Imagen `qsrr-jobs` de las tareas Python de Kestra (simulación, monitoreo, reentrenamiento). |
| `api` | 8000 | Servicio de predicción (FastAPI). Carga `models:/qsrr-predict-modelo@champion`. |
| `tablero` | 8501 | Tablero de monitoreo (Streamlit). Sin Snowflake, lee `docs/*.csv`. |

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

## 2. EDA y modelo

Los notebooks `01`–`05` (EDA, features, líneas base, tuning y selección) vienen
del PSet 3. El champion vigente se registra con los hiperparámetros del PSet 3
sobre la OBT corregida y el split por experimento:

```bash
python -m scripts.registrar_champion      # registra la versión y le asigna el alias champion
python -m monitoreo.deriva calibrar       # referencia de deriva y umbrales (monitoreo/referencia.json)
python -m scripts.exportar_fixture        # copia del modelo para CI (tests/fixtures/)
```

## 3. Registro → API → simulación → monitoreo → reentrenamiento

1. **API.** `docker compose up -d api`. Ejemplo:
   `curl localhost:8000/modelo` y `POST localhost:8000/predecir` (esquema en
   `api/esquemas.py`; documentación interactiva en `localhost:8000/docs`).
2. **Simulación.** En Kestra, ejecuta **`produccion_lotes`**
   (`preparar=true`, semanas 1–11). Cada semana predice un lote vía la API,
   publica los targets del lote anterior y llama a **`monitoreo`**. Cuando el
   desempeño cae 2 lotes seguidos, `monitoreo` lanza **`reentrenamiento`**, que
   se detiene en la tarea de aprobación: reanúdala en la interfaz de Kestra con
   `aprobar=true/false` y un motivo.
3. **Tablero.** `http://localhost:8501`.
4. **Evidencia.** `python -m scripts.exportar_evidencia` escribe en `docs/`
   `predicciones.csv`, `monitoreo.csv`, `alertas.csv`, `corridas.csv` y
   `reentrenamientos.csv`.
5. **Análisis.** `notebooks/06_simulacion_produccion.ipynb` (lotes, deriva
   inducida, trazabilidad y rollback) y `notebooks/07_analisis_monitoreo.ipynb`
   (deriva, alertas, reentrenamiento, ética y resultado de negocio). Resumen en
   [`docs/simulacion.md`](docs/simulacion.md).

**Rollback** (sin reconstruir la imagen): mueve el alias en MLflow; la API lo
toma en ≤ 30 s, o al instante con `POST /admin/recargar`.

```python
MlflowClient().set_registered_model_alias("qsrr-predict-modelo", "champion", "2")
```

**Interruptor de respaldo** (regla de negocio en lugar del modelo):
`USAR_RESPALDO=true` en `.env` y `docker compose up -d api`, o
`curl -X POST "localhost:8000/admin/respaldo?activo=true" -H "X-Admin-Token: $ADMIN_TOKEN"`.

## Entregables (docs/)

| Archivo | Cómo se genera |
|---|---|
| `PSet4_memo_Buenaño_Peñafiel.pdf` | `python -m scripts.construir_memo --video <URL>` desde `docs/memo_pset4.md` (anexos: memos de `historial/`, capturas y `cambios.md`) |
| `PSet4_presentacion_Buenaño_Peñafiel.pdf` | `python -m scripts.construir_presentacion` |
| `arquitectura.png`, `modelo_dimensional.png` | `python -m scripts.diagramas --png` |
| `capturas/*.png` | `python -m scripts.capturas` (infraestructura arriba; `playwright` + Chrome) |
| `*.csv` de evidencia | `python -m scripts.exportar_evidencia` |

## Pruebas

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/
```

En CI (`.github/workflows/ci.yml`, en la raíz del repositorio porque GitHub
Actions solo lee esa carpeta) las pruebas usan la copia del modelo de
`tests/fixtures/`, sin MLflow ni Snowflake. `cd.yml` publica la imagen de la API
en GHCR con el hash del commit en cada merge a `master` con CI en verde; para
usarla, pon `API_IMAGE_TAG=<hash>` en `.env`.

Los notebooks 06 y 07 usan el kernel del venv del proyecto:
`.venv/bin/python -m ipykernel install --sys-prefix --name proyecto-final`.
