import os

from pyspark.sql import SparkSession


required_settings = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
)
missing_settings = [name for name in required_settings if not os.environ.get(name)]
if missing_settings:
    raise RuntimeError(
        "Missing required Snowflake environment variables: "
        + ", ".join(missing_settings)
    )

spark = (
    SparkSession.builder.appName("QSRR_OBT_Processing")
    .getOrCreate()
)

snowflake_options = {
    "sfUrl": f"{os.environ['SNOWFLAKE_ACCOUNT']}.snowflakecomputing.com",
    "sfUser": os.environ["SNOWFLAKE_USER"],
    "sfPassword": os.environ["SNOWFLAKE_PASSWORD"],
    "sfDatabase": os.environ["SNOWFLAKE_DATABASE"],
    "sfWarehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
    "sfRole": os.environ["SNOWFLAKE_ROLE"],
}
read_options = {**snowflake_options, "sfSchema": "GOLD"}
write_options = {**snowflake_options, "sfSchema": "GOLD"}

obt_query = """
    WITH dim_compuesto_unico AS (
        SELECT COMPUESTO_ID, INCHIKEY, NOMBRE_COMPUESTO
        FROM DIM_COMPUESTO
        WHERE COMPUESTO_ID IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY COMPUESTO_ID
            ORDER BY NOMBRE_COMPUESTO ASC NULLS LAST, INCHIKEY
        ) = 1
    ),
    dim_condiciones_unicas AS (
        SELECT CONDICION_ID, TIPO_COLUMNA, FASE_MOVIL, FLUJO_ML_MIN
        FROM DIM_CONDICIONES
        WHERE CONDICION_ID IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY CONDICION_ID
            ORDER BY TIPO_COLUMNA, FASE_MOVIL, FLUJO_ML_MIN
        ) = 1
    )
    SELECT
        f.HECHO_ID,
        c.INCHIKEY,
        c.NOMBRE_COMPUESTO,
        cond.TIPO_COLUMNA,
        cond.FASE_MOVIL,
        cond.FLUJO_ML_MIN,
        f.TIEMPO_RETENCION,
        f.FACTOR_RETENCION
    FROM FACT_RETENCION_CROMATOGRAFICA AS f
    LEFT JOIN dim_compuesto_unico AS c
        ON f.COMPUESTO_ID = c.COMPUESTO_ID
    LEFT JOIN dim_condiciones_unicas AS cond
        ON f.CONDICION_ID = cond.CONDICION_ID
"""

df_obt = (
    spark.read.format("snowflake")
    .options(**read_options)
    .option("query", obt_query)
    .load()
)

(
    df_obt.write.format("snowflake")
    .options(**write_options)
    .option("dbtable", "OBT_QSRR_FINAL")
    .mode("overwrite")
    .save()
)

print("Proceso OBT completado y guardado en Snowflake.")
spark.stop()
