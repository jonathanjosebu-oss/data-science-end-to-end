# PSet 2 — Ingesta de RepoRT a Snowflake

## Qué permite reproducir el enlace

El repositorio contiene el código para reconstruir el pipeline, pero abrir el
enlace no inicia una ejecución ni concede acceso a Snowflake. Quien lo evalúe
configura credenciales propias en `.env` y ejecuta `docker compose up -d
--build`. Compose construye las imágenes de dbt y Spark, levanta Kestra e
importa automáticamente los flows y sus archivos. Desde Kestra, un solo flow
ejecuta la ingesta, `dbt build` y el job Spark.

El flow descarga los archivos `*_rtdata_canonical_success.tsv` de RepoRT
(rama `master`, carpeta `processed_data/`) con los metadatos de columna y fase
móvil de cada experimento. Cada ejecución carga el commit de RepoRT vigente en
su fecha lógica como una partición `SNAPSHOT_DATE` de `RAW_REPORT_DATA`. Las
reglas de limpieza viven en dbt.
No ejecutes el antiguo `ingestar.py` de la raíz: requiere un `report.csv` local
que RepoRT no publica.

## 1. Credenciales

**Rota la contraseña de Snowflake que estaba escrita en el antiguo
`.env.example`.** No reutilices esa contraseña.

Desde esta carpeta:

```bash
cp .env.example .env
```

Completa `.env` con el identificador de cuenta mostrado antes de
`.snowflakecomputing.com` en la URL de tu cuenta, el usuario, una contraseña
nueva y un rol con permisos para usar el warehouse/database/schema y crear un
stage, tablas y un formato de archivo en el esquema Raw y crear esquemas y
tablas para dbt. `SNOWFLAKE_DATABASE` indica la base destino y
`SNOWFLAKE_SCHEMA=RAW` es el esquema inicial de dbt. Define también
`KESTRA_USER` (un email) y `KESTRA_PASSWORD`, que son las credenciales de la
UI y la API de Kestra. No subas `.env`; está excluido por `.gitignore`.

Las tablas se crean en la cuenta Snowflake indicada por estas variables; no se
copian automáticamente a la cuenta del profesor. Para revisar los objetos ya
creados, el profesor debe tener acceso concedido a esa cuenta/base de datos. Si
ejecuta la entrega con su propia cuenta, el pipeline crea los objetos en su
cuenta con sus permisos y créditos.

## 2. Levantar la infraestructura e importar los flows

```bash
docker compose config --quiet
docker compose up -d --build
docker compose logs kestra-deploy   # debe terminar con "Despliegue completo."
```

Servicios de `docker-compose.yml`:

| Servicio | Función |
|---|---|
| `dbt-image` | Construye `pset2-dbt:1.11` (dbt-core 1.11.6 + dbt-snowflake 1.11.4) y termina. |
| `spark` | Construye `pset2-spark:3.5.3` con el conector de Snowflake ya incluido. |
| `kestra` | Kestra 2.0.7 con autenticación básica tomada de `.env`. Lanza las tareas en contenedores mediante el socket de Docker; úsalo solo en un entorno local confiable. |
| `kestra-deploy` | Ejecuta [`kestra/deploy.sh`](kestra/deploy.sh) cuando Kestra está sano. Sube los archivos de namespace (`ingest_repo_rt.py`, el proyecto `dbt/` y `spark/obt_processing.py`), valida los flows y los importa. |
| `dbt` (perfil `manual`) | Permite ejecutar dbt a mano: `docker compose run --rm dbt dbt build`. |

Si cambias el código de los flows, dbt o Spark, vuelve a desplegar con
`docker compose run --rm kestra-deploy`. Si cambias el Dockerfile de dbt o de
Spark, ejecuta antes `docker compose build`. Abre el puerto 8080 para la UI.
Los diagramas están en [`docs/arquitectura.svg`](docs/arquitectura.svg) y
[`docs/modelo_estrella.svg`](docs/modelo_estrella.svg).

## 3. Ejecutar el pipeline (Kestra)

Flow [`ingest_report_to_snowflake`](kestra/flows/ingest_report_to_snowflake.yml),
namespace `pset2.pipeline`:

1. `ensure_snowflake_objects`: crea el stage, el formato CSV y la tabla Raw, y
   agrega las columnas de linaje (`SNAPSHOT_DATE`, `SOURCE_REF`,
   `SOURCE_COMMIT`, `EXECUTION_ID`, `INGESTED_AT`) si faltan.
2. `extract_dataset`: resuelve `source_ref` al último commit hasta la fecha
   lógica y descarga sus TSV.
3. Carga en el stage, `COPY INTO` a una tabla transient de la ejecución y luego
   `publish_snapshot`. Esta tarea reemplaza en una transacción **solo** la
   partición `SNAPSHOT_DATE` de esa fecha.
4. `transformations` (si `run_transformations = true`): `dbt_build` construye
   Bronze, Silver y Gold y ejecuta las 44 pruebas; `spark_obt` construye la OBT.
5. Bloque `errors`: si falla cualquier tarea, registra la tarea y el snapshot
   afectados y borra la tabla transient y los archivos del stage.

La fecha lógica es el input `snapshot_date`; si no se indica, se usa la fecha
del trigger o la de inicio de la ejecución. El trigger corre cada lunes a las
02:00 UTC. Los pasos de red y Snowflake reintentan hasta tres veces.

### Backfill histórico

El flow [`backfill_report_history`](kestra/flows/backfill_report_history.yml)
recibe `start_date`, `end_date` y `step` (`WEEK`, `MONTH` o `QUARTER`). Ejecuta
la ingesta para cada fecha, una a la vez y sin transformaciones, y cada fecha
queda en su propia partición de Raw. Con `rebuild_gold = true`, al final
ejecuta una vez la ingesta del día con dbt y Spark. Como el flow principal usa
`trigger.date`, también funciona el backfill nativo del trigger
`weekly_schedule` desde la UI.

```sql
SELECT SNAPSHOT_DATE, SOURCE_COMMIT, COUNT(*)
FROM REPORT_QSRR_DB.RAW.RAW_REPORT_DATA GROUP BY 1, 2 ORDER BY 1;
```

## 4. dbt: Bronze, Silver y Gold

| Capa | Modelo | Contenido |
|---|---|---|
| Bronze | `stg_report_data` | Un snapshot de Raw (variable `snapshot_date`, por defecto el más reciente), con nombres y tipos estandarizados y **sin descartar filas**. `t0 = 0` se convierte en nulo. |
| Silver | `int_registros_clasificados` | Una fila por registro Bronze con su `motivo_exclusion` (nulo = se conserva). |
| Silver | `int_retencion_filtrada` | Una fila por `(experimento, compuesto)`, con las réplicas consistentes colapsadas en la mediana. |
| Gold | `fact_retencion_cromatografica`, `dim_compuesto`, `dim_condiciones` | Esquema estrella; el hecho tiene el grano de Silver. |

Reglas de limpieza (los umbrales son `vars` en `dbt/dbt_project.yml`):
`rt_no_positivo`, `sin_inchikey`, `no_retenido_rt_menor_igual_t0`
(RT ≤ t0 cuando t0 es conocido), `rt_fuera_de_rango` (> 120 min) y
`replicas_inconsistentes` (mismo compuesto en el mismo experimento con un rango
> 0.5 min). El flujo se normaliza a mL/min: un valor > 5 se interpreta como
µL/min.

Pruebas de dominio, además de `not_null`, `unique` y `relationships`:
- `en_rango` (genérica) sobre RT, flujo y rango de réplicas.
- Conservación de filas Raw → Bronze → auditoría → Silver → Gold.
- RT > t0.
- Metadatos constantes por experimento.
- Valores aceptados de `motivo_exclusion`.
- Un tope del 10 % de exclusiones.

Para ejecutar dbt fuera de Kestra:

```bash
docker compose run --rm dbt dbt build
# o con dbt local:
mkdir -p dbt/config && cp dbt/profiles.yml.example dbt/config/profiles.yml
set -a; source .env; set +a
cd dbt && dbt build --profiles-dir config && cd ..
```

## 5. Spark y OBT

[`spark/obt_processing.py`](spark/obt_processing.py) lee el hecho y las dos
dimensiones de `GOLD` y, **antes de unir**, valida:
- La unicidad y no nulidad de `COMPUESTO_ID`, `INCHIKEY`, `CONDICION_ID` y
  `HECHO_ID`.
- Que no haya hechos sin dimensión.

Después del join verifica que la OBT tenga exactamente las filas del hecho. Si
algo falla, termina con código 1 **sin escribir**, y la OBT anterior queda
intacta. No deduplica con `ROW_NUMBER()`. Para ejecutarlo a mano:

```bash
docker compose run --rm spark /opt/spark/bin/spark-submit /opt/pset2/spark/obt_processing.py
```

## 6. Documento técnico y resumen

El memo de hasta seis páginas, diagramas y limitaciones está en `docs/`. El
archivo `PSet2_memo_Buenaño_Peñafiel.pdf` sigue el patrón de nombre pedido por
la rúbrica usando los apellidos del estudiante.

Para regenerar el PDF desde el memo editable:

```bash
python -m pip install -r docs/requirements.txt
python docs/generate_memo.py
```

`docs/PSet2_anexos_Buenaño_Peñafiel.pdf` reúne la evidencia de ejecución:
- La última ejecución completa en Kestra, con las validaciones de Spark.
- El backfill y una ejecución fallida en la que actuó el bloque `errors`.
- El resultado de cada modelo y prueba de dbt (el `run_results.json` que Kestra
  guarda para la tarea `dbt_build`).
- Consultas de verificación en Snowflake.

Los datos salen de `docs/evidencia/*.json`. Si agregas capturas en
`docs/capturas/` (PNG o JPG, con pies en `pies.json`), se incluyen como
sección A; las capturas anteriores a la corrección están en
`docs/capturas/obsoletas/` y no se incluyen. Para recolectar la evidencia de
nuevo necesitas Kestra corriendo y `.env` exportado:

```bash
python docs/generate_anexos.py --refresh   # o sin --refresh para solo rearmar el PDF
```

## 7. Prueba local de descarga

Antes de enviar todo el repositorio a Snowflake, se puede verificar la descarga
y el formato con dos experimentos:

```bash
python kestra/flows/ingest_repo_rt.py master /tmp/reporrt-smoke.csv --max-experiments 2 --as-of 2025-01-01
```

Este comando solo prueba la fuente pública y **no** se conecta a Snowflake.
Kestra ejecuta el script sin `--max-experiments`, por lo que carga todos los
experimentos canónicos exitosos encontrados en RepoRT.

## Esquema y alcance de Raw

`RAW_REPORT_DATA` incluye el ID de experimento, las mediciones y la estructura
química estandarizadas de RepoRT, la columna, el flujo, el tiempo muerto y la
composición de H2O/MeOH/ACN de las fases A y B. Además guarda el linaje de cada
partición (`SNAPSHOT_DATE`, `SOURCE_COMMIT`, `EXECUTION_ID`, `INGESTED_AT`).
RepoRT no publica el factor de retención, así que ese campo se eliminó del
modelo en lugar de mantener una columna siempre nula.

## Calidad observada en el snapshot actual (commit `420b550`)

| Resultado | Filas |
|---|---:|
| Raw / Bronze | 183,199 |
| Excluidas por RT ≤ t0 | 3,912 (151 experimentos) |
| Excluidas por réplicas inconsistentes | 5,117 (129 experimentos) |
| Excluidas por RT no positivo | 1 |
| Conservadas (4.9 % excluido) | 174,169 |
| Silver / hecho / OBT después de colapsar réplicas | 166,137 |
| `DIM_COMPUESTO` / `DIM_CONDICIONES` | 96,855 / 151 |

El 49.5 % de las filas no tiene nombre, el 1.4 % no tiene columna y el 6.6 % no
tiene flujo. Son atributos descriptivos: se conservan como nulos y no se
inventan. No hubo valores de flujo que requirieran conversión de unidades. La
precisión analítica no se contrastó con una referencia externa.
