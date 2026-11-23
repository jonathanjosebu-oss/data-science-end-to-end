"""Construye OBT_QSRR_FINAL a partir del star schema Gold.

Antes de unir, valida que cada dimensión tenga claves únicas y no nulas y que
cada hecho encuentre su compuesto y su condición. Si alguna validación falla,
el job termina con error *antes* de escribir: la OBT anterior queda intacta.
No se deduplica con ROW_NUMBER(): un duplicado es un error del modelo, no algo
que el job deba ocultar.
"""

from __future__ import annotations

import os
import sys

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


REQUIRED_SETTINGS = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
)
GOLD_SCHEMA = "GOLD"
OBT_TABLE = "OBT_QSRR_FINAL"


class ValidationError(RuntimeError):
    """Una o más validaciones de integridad fallaron."""


def snowflake_options() -> dict[str, str]:
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Missing required Snowflake environment variables: " + ", ".join(missing)
        )
    return {
        "sfUrl": f"{os.environ['SNOWFLAKE_ACCOUNT']}.snowflakecomputing.com",
        "sfUser": os.environ["SNOWFLAKE_USER"],
        "sfPassword": os.environ["SNOWFLAKE_PASSWORD"],
        "sfDatabase": os.environ["SNOWFLAKE_DATABASE"],
        "sfWarehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "sfRole": os.environ["SNOWFLAKE_ROLE"],
        "sfSchema": GOLD_SCHEMA,
    }


def read_table(spark: SparkSession, options: dict[str, str], table: str) -> DataFrame:
    return spark.read.format("snowflake").options(**options).option("dbtable", table).load()


def key_failures(df: DataFrame, table: str, key: str) -> list[str]:
    """Devuelve los problemas de unicidad / nulidad de `key` en `df`."""
    stats = df.agg(
        F.count(F.lit(1)).alias("filas"),
        F.countDistinct(key).alias("distintos"),
        F.sum(F.col(key).isNull().cast("int")).alias("nulos"),
    ).first()
    filas, distintos, nulos = stats["filas"], stats["distintos"], stats["nulos"] or 0
    print(f"[validación] {table}.{key}: filas={filas} distintos={distintos} nulos={nulos}")

    failures = []
    if filas == 0:
        failures.append(f"{table} está vacía")
    if nulos:
        failures.append(f"{table}.{key} tiene {nulos} valores nulos")
    if distintos != filas - nulos:
        duplicados = (
            df.where(F.col(key).isNotNull())
            .groupBy(key)
            .count()
            .where(F.col("count") > 1)
            .orderBy(F.desc("count"))
            .limit(5)
            .collect()
        )
        ejemplos = ", ".join(f"{row[key]} (x{row['count']})" for row in duplicados)
        failures.append(
            f"{table}.{key} tiene {filas - nulos - distintos} filas duplicadas; "
            f"ejemplos: {ejemplos}"
        )
    return failures


def orphan_failures(fact: DataFrame, dim: DataFrame, key: str, dim_name: str) -> list[str]:
    huerfanos = fact.join(dim.select(key), on=key, how="left_anti").count()
    print(f"[validación] hechos sin {dim_name}: {huerfanos}")
    if huerfanos:
        return [f"{huerfanos} hechos no encuentran su fila en {dim_name} por {key}"]
    return []


def main() -> int:
    options = snowflake_options()
    spark = SparkSession.builder.appName("QSRR_OBT_Processing").getOrCreate()
    try:
        fact = read_table(spark, options, "FACT_RETENCION_CROMATOGRAFICA").cache()
        dim_compuesto = read_table(spark, options, "DIM_COMPUESTO").cache()
        dim_condiciones = read_table(spark, options, "DIM_CONDICIONES").cache()
        dim_metodo = read_table(spark, options, "DIM_METODO").cache()

        # 1. Validaciones previas a los joins.
        failures: list[str] = []
        failures += key_failures(dim_compuesto, "DIM_COMPUESTO", "COMPUESTO_ID")
        failures += key_failures(dim_compuesto, "DIM_COMPUESTO", "INCHIKEY")
        failures += key_failures(dim_condiciones, "DIM_CONDICIONES", "CONDICION_ID")
        failures += key_failures(dim_metodo, "DIM_METODO", "EXPERIMENTO_ID")
        failures += key_failures(fact, "FACT_RETENCION_CROMATOGRAFICA", "HECHO_ID")
        failures += orphan_failures(fact, dim_compuesto, "COMPUESTO_ID", "DIM_COMPUESTO")
        failures += orphan_failures(fact, dim_condiciones, "CONDICION_ID", "DIM_CONDICIONES")
        failures += orphan_failures(fact, dim_metodo, "EXPERIMENTO_ID", "DIM_METODO")
        if failures:
            raise ValidationError("; ".join(failures))

        # 2. Joins: con claves únicas validadas, un inner join conserva el grano.
        obt = (
            fact.join(dim_compuesto, on="COMPUESTO_ID", how="inner")
            .join(dim_condiciones, on="CONDICION_ID", how="inner")
            .join(dim_metodo, on="EXPERIMENTO_ID", how="inner")
            .select(
                "HECHO_ID",
                "EXPERIMENTO_ID",
                "INCHIKEY",
                "NOMBRE_COMPUESTO",
                "TIPO_COLUMNA",
                "FASE_MOVIL",
                "FLUJO_ML_MIN",
                "TIEMPO_RETENCION",
                "N_MEDICIONES",
                "RANGO_REPLICAS_MIN",
                "T0_MIN",
                "COLUMNA_LONGITUD_MM",
                "COLUMNA_DIAMETRO_MM",
                "COLUMNA_PARTICULA_UM",
                "PH_A",
                "PH_B",
                "GRADIENTE",
                "SNAPSHOT_DATE",
                "SOURCE_COMMIT",
            )
            .cache()
        )

        # 3. Validación posterior: la OBT mantiene exactamente el grano del hecho.
        filas_hecho = fact.count()
        filas_obt = obt.count()
        print(f"[validación] filas hecho={filas_hecho} filas OBT={filas_obt}")
        if filas_obt != filas_hecho:
            raise ValidationError(
                f"La OBT tiene {filas_obt} filas y el hecho {filas_hecho}; "
                "los joins cambiaron el grano"
            )

        # 4. Solo se escribe si todas las validaciones pasaron.
        (
            obt.write.format("snowflake")
            .options(**options)
            .option("dbtable", OBT_TABLE)
            .mode("overwrite")
            .save()
        )
        print(f"OBT {GOLD_SCHEMA}.{OBT_TABLE} escrita con {filas_obt} filas.")
        return 0
    except ValidationError as error:
        print(f"[validación] FALLÓ, no se escribe la OBT: {error}", file=sys.stderr)
        return 1
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
