# PSet 2 — Resumen de implementación

## Resultado

Se implementó un pipeline ELT por lotes para preparar datos de retención
cromatográfica de RepoRT en Snowflake:

**RepoRT → Kestra → Snowflake RAW → dbt BRONZE → dbt SILVER → dbt GOLD → Spark → OBT**

Kestra, dbt y Spark se ejecutan en el entorno local/Docker. Las tablas de datos
resultantes y las capas procesadas viven en Snowflake. El código reproducible y
la documentación se entregan en este repositorio.

## Componentes

- **Kestra:** descarga los archivos canónicos de RepoRT y sus metadatos,
  realiza la carga mediante un named stage y `COPY INTO`, y reemplaza el
  snapshot `RAW.RAW_REPORT_DATA` al completar la carga. Tiene trigger semanal
  los lunes a las 02:00 UTC, reintentos y entrada `source_ref` para repetir
  una versión histórica por rama o SHA.
- **dbt:** lee Raw usando `source()` y relaciona modelos con `ref()`.
  Construye `BRONZE.STG_REPORT_DATA`, `SILVER.INT_RETENCION_FILTRADA`, y en
  `GOLD` la tabla de hechos y dos dimensiones. El grano de Silver/Hechos es una
  medición canónica por clave de origen `(experiment_id, id)`. Silver conserva
  las mediciones positivas, sin colapsar mediciones diferentes del mismo
  compuesto.
- **Spark:** ejecuta el join de la tabla de hechos y las dimensiones Gold y
  escribe `GOLD.OBT_QSRR_FINAL`. El join preserva una fila por `HECHO_ID`.
- **Docker Compose:** levanta Kestra y Spark 3.5.3. dbt Core se ejecuta en la
  terminal del entorno usando el perfil de ejemplo.

## Conteos comprobados en Snowflake

| Objeto | Filas |
|---|---:|
| `RAW.RAW_REPORT_DATA` | 183,199 |
| `BRONZE.STG_REPORT_DATA` | 183,199 |
| `SILVER.INT_RETENCION_FILTRADA` | 183,198 |
| `GOLD.FACT_RETENCION_CROMATOGRAFICA` | 183,198 |
| `GOLD.DIM_COMPUESTO` | 97,688 |
| `GOLD.DIM_CONDICIONES` | 151 |
| `GOLD.OBT_QSRR_FINAL` | 183,198 |

El único registro excluido en Silver tiene tiempo de retención no positivo.
`dbt build` pasó 22 de 22 acciones de modelos/pruebas. Las claves de hechos y
dimensiones son únicas/no nulas y las dos pruebas `relationships` pasaron.
En la OBT, `HECHO_ID` es único y no nulo; 2,603 filas mantienen atributos de
columna nulos porque la fuente no los proporciona.

## Calidad de la fuente

En la instantánea inspeccionada no se encontraron duplicados por
`(experiment_id, id)`, tiempos de retención nulos ni InChIKey ausentes. Se
observaron 90,640 nombres vacíos (49.5%), 2,603 nombres de columna vacíos
(1.4%) y 12,177 flujos ausentes o no positivos (6.6%). No se inventan valores.
No se validó la precisión analítica contra mediciones externas de referencia;
esa limitación queda explícita en el memo.

## Reproducir

1. Copiar `.env.example` a `.env` y completarlo con credenciales propias de
   Snowflake. No subir `.env`.
2. Ejecutar `docker compose up -d --build`.
3. Importar el flow y el archivo Python de Kestra siguiendo `README.md`, y
   ejecutar con `source_ref=master` o un SHA de RepoRT.
4. Crear `dbt/config/profiles.yml` desde el ejemplo, exportar `.env` en la
   terminal y ejecutar `dbt debug --profiles-dir config` y
   `dbt build --profiles-dir config` desde `dbt/`.
5. Ejecutar Spark:

```bash
docker compose run --rm spark /opt/spark/bin/spark-submit \
  --packages net.snowflake:spark-snowflake_2.12:3.2.3-spark_3.5 \
  /opt/pset2/spark/obt_processing.py
```
6. Verificar conteo y unicidad de la OBT en Snowflake:

```sql
SELECT COUNT(*) AS total_filas,
       COUNT(DISTINCT hecho_id) AS hechos_unicos
FROM REPORT_QSRR_DB.GOLD.OBT_QSRR_FINAL;
```

El profesor debe ejecutar el pipeline con su propia cuenta/rol/permisos; las
tablas de Snowflake de una cuenta no se transfieren al repositorio ni se
comparten automáticamente con otra cuenta.

## Archivos de entrega

- `README.md`: instrucciones de ejecución.
- `docs/PSet2_memo_Buenano_Penafiel_Jonatan.pdf`: memo técnico de hasta seis
  páginas.
- `docs/memo_tecnico.md`: fuente editable del memo.
- `docs/arquitectura.svg` y `docs/modelo_estrella.svg`: diagramas solicitados.

Si el nombre recibido para el PDF no corresponde a los apellidos del
estudiante, renombrarlo antes de entregar. No se incluye `.env`.
