# PSet 2 — Ingesta de RepoRT a Snowflake

Este flujo carga a Snowflake una instantánea completa de los experimentos RepoRT
que tienen mediciones de retención canónicas exitosas. La URL anterior apuntaba a
`main/data/report.csv`, que no existe: RepoRT usa la rama `master` y publica los
datos como TSV por experimento en `processed_data/`.

El flujo descarga y combina los archivos `*_rtdata_canonical_success.tsv` con
los metadatos de columna y fase móvil de cada experimento. Escribe un CSV en el
almacenamiento de Kestra, lo sube al named stage `REPORT_INGEST_NAMED_STAGE` y
crea `RAW_REPORT_DATA` en Snowflake. La tabla Raw se reemplaza como una sola
operación al terminar la carga, de modo que una falla anterior no deja una tabla
truncada. La limpieza y las reglas de negocio permanecen en dbt.
No ejecutes el antiguo `ingestar.py` de la raíz para esta carga: requiere un
`report.csv` local que RepoRT no publica; el flow usa el script indicado abajo.

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
`SNOWFLAKE_SCHEMA=RAW` es el esquema inicial de dbt. No subas `.env`; está
excluido por `.gitignore`.

Las tablas se crean en la cuenta Snowflake indicada por estas variables; no se
copian automáticamente a la cuenta del profesor. Para revisar los objetos ya
creados, el profesor debe tener acceso concedido a esa cuenta/base de datos. Si
ejecuta la entrega con su propia cuenta, el pipeline crea los objetos en su
cuenta con sus permisos y créditos.

## 2. Levantar la infraestructura local

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs -f kestra
```

Abre el puerto 8080 desde VS Code/Codespaces. La configuración levanta Kestra
en modo local con H2 persistente y un contenedor Spark 3.5.3 listo para ejecutar
el job en modo local. El socket de Docker está montado en Kestra porque las
tareas Python usan el runner Docker; úsalo solo en un entorno local confiable.
El servicio Spark monta el proyecto en modo solo lectura y lee `.env` local,
que nunca debe agregarse al repositorio.

Si actualizas `.env`, recrea el contenedor para que lea las variables nuevas:

```bash
docker compose up -d --force-recreate
```

El diagrama de infraestructura está en [`docs/arquitectura.svg`](docs/arquitectura.svg)
y el diagrama dimensional en [`docs/modelo_estrella.svg`](docs/modelo_estrella.svg).

## 3. Importar y ejecutar el flow

En Kestra, importa `kestra/flows/ingest_report_to_snowflake.yml` en el namespace
`pset2.pipeline`. Luego agrega
`kestra/flows/ingest_repo_rt.py` como archivo de namespace con ese mismo nombre;
el flow lo incluye mediante `namespaceFiles`.

Ejecuta el flow manualmente con `source_ref=master` para la primera carga. Para
reproducir una versión histórica, usa como `source_ref` el SHA de un commit de
RepoRT. Después de la primera carga, el trigger lo ejecuta cada lunes a las
02:00 UTC. Los pasos de red y Snowflake reintentan hasta tres veces.

El permiso para crear el stage se necesita una sola vez. La carga crea un named
stage `REPORT_INGEST_NAMED_STAGE` y un formato CSV con nombre para leer el
archivo comprimido. No usa el stage de tabla (`@%...`), que no permite copiar
sus archivos a una tabla transient distinta.
`COPY INTO` carga primero las columnas del CSV como texto en una tabla transient
por ejecución; después la consulta convierte las columnas numéricas y reemplaza
`RAW_REPORT_DATA`. Así, la tabla final solo se reemplaza después de completar la
carga del archivo. Al correr el flow otra vez no duplica filas. En caso de error,
revisa la tarea fallida en la UI de Kestra; el flow no registra la contraseña.

## 4. Construir Bronze, Silver y Gold con dbt

Las tres capas se materializan en Snowflake, en la base indicada por
`SNOWFLAKE_DATABASE`: `BRONZE`, `SILVER` y `GOLD`. La fuente Raw se lee desde
`RAW`. dbt crea los esquemas si el rol tiene permiso `CREATE SCHEMA` en la base.
Silver conserva una fila por `registro_id` con tiempo de retención positivo;
no colapsa mediciones distintas solo porque compartan compuesto y columna.
Gold declara el grano de la tabla de hechos como una medición canónica por
registro de RepoRT, con dimensiones de compuesto y condición.
Antes de ejecutar dbt, configura su perfil sin copiar credenciales al repositorio:

```bash
mkdir -p dbt/config
cp dbt/profiles.yml.example dbt/config/profiles.yml
set -a
source .env
set +a
cd dbt
dbt debug --profiles-dir config
dbt build --profiles-dir config
```

El ejemplo de perfil utiliza variables de entorno; si cambias `.env`, vuelve a
la raíz del PSet y cárgalo de nuevo. El perfil local queda en `dbt/config/` y
está excluido de Git; no sobrescribe la configuración personal `~/.dbt`. `dbt
build` crea las tablas de capa en Snowflake.
`source()` enlaza Raw y `ref()` enlaza los modelos entre capas.
Cuando termines, vuelve a la carpeta raíz del PSet antes de ejecutar Spark:

```bash
cd ..
```

## 5. Construir la OBT con Spark

Después de que `dbt build` termine correctamente, ejecuta Spark desde esta
carpeta. El script lee la tabla de hechos y las dimensiones Gold del esquema
`GOLD` y escribe
`OBT_QSRR_FINAL` en `GOLD`. Lee las credenciales de
Snowflake desde `.env`; no escribas la contraseña directamente en el script.

```bash
docker compose run --rm spark /opt/spark/bin/spark-submit \
  --packages net.snowflake:spark-snowflake_2.12:3.2.3-spark_3.5 \
  /opt/pset2/spark/obt_processing.py
```

El contenedor incluye Spark y Java; el conector se descarga de Maven Central en
la primera ejecución. El proceso escribe la OBT mediante el conector de
Snowflake.
Para comprobar la tabla final en Snowflake (se espera que filas y hechos únicos
coincidan; para el snapshot actual deberían ser 183,198 después de filtrar el
único tiempo de retención no positivo):

```sql
SELECT COUNT(*) AS TOTAL_FILAS, COUNT(DISTINCT HECHO_ID) AS HECHOS_UNICOS
FROM REPORT_QSRR_DB.GOLD.OBT_QSRR_FINAL;
```

No subas `.env` ni compartas la contraseña.

## 6. Documento técnico y resumen

El memo de hasta seis páginas, diagramas y limitaciones está en `docs/`. El
archivo `PSet2_memo_Buenano_Penafiel_Jonatan.pdf` sigue el patrón de nombre
pedido por la rúbrica usando los apellidos proporcionados para la entrega.
`README1.md` resume implementación, comandos y resultados validados. Si el
nombre proporcionado para el PDF no corresponde a los apellidos del estudiante,
renómbralo antes de enviar.

Para regenerar el PDF desde el memo editable:

```bash
python -m pip install -r docs/requirements.txt
python docs/generate_memo.py
```

## 7. Prueba local de descarga

Antes de enviar todo el repositorio a Snowflake, se puede verificar la descarga
y el formato con dos experimentos:

```bash
python kestra/flows/ingest_repo_rt.py master /tmp/reporrt-smoke.csv --max-experiments 2
```

Este comando solo prueba la fuente pública y **no** se conecta a Snowflake.
Kestra ejecuta el script sin `--max-experiments`, por lo que carga todos los
experimentos canónicos exitosos encontrados en RepoRT.

## Esquema y alcance de Raw

`RAW_REPORT_DATA` incluye el ID de experimento, las mediciones y estructura
química estandarizadas publicadas por RepoRT, además del nombre/código y
dimensiones de columna, flujo, tiempo muerto y composición de H2O/MeOH/ACN de
las fases A y B. Los campos se conservan como texto para datos descriptivos y
numéricos para RT/condiciones. La fuente canónica no proporciona un índice de
retención; por ello `factor_retencion` queda nulo en Staging, no se inventa.

La capa Bronze en dbt adapta los nombres de RepoRT al modelo del proyecto y
valida la existencia del tiempo de retención. La fuente es un snapshot público
mutable: para reproducir una carga idéntica, fija `source_ref` al SHA del commit
utilizado.

## Calidad observada en el snapshot procesado

En la instantánea cargada de 183,199 filas: no se encontraron claves duplicadas
por `(experiment_id, id)`, ni `RT` nulo, ni `InChIKey` ausente. Se encontró un
`RT` no positivo, que Silver excluye por no representar una retención válida.
`NAME` estaba vacío en 90,640 filas (49.5%); `COLUMN_NAME`, en 2,603 (1.4%);
y el flujo estaba ausente o no era positivo en 12,177 (6.6%). Esos atributos
descriptivos no se inventan ni se usan para eliminar mediciones; en la OBT los
campos de columna pueden permanecer nulos. La fuente publica mediciones
canónicas exitosas, pero no se hizo una comparación independiente con una
medición de referencia para certificar su precisión analítica.

Con la regla de Silver actual se conservan 183,198 observaciones. Las
dimensiones Gold tienen claves no nulas y únicas; las pruebas `relationships`
validan que cada hecho encuentre su compuesto y condición, incluso cuando los
atributos descriptivos de esa condición estén ausentes.
