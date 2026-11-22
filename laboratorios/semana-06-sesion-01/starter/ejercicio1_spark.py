"""Ejercicio 1: un job de Spark sobre ventas.csv.

Corre el script antes de tocar nada:

    python3 ejercicio1_spark.py

Corre sin errores y sin los TODO resueltos. Fijate en que numeros salen
asi, antes de completar cada TODO.
"""

import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.appName("ventas-por-categoria").master("local[*]").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

ventas = spark.read.csv("ventas.csv", header=True, inferSchema=True) #header dice que la primera fila tiene los nombres de las columnas
ventas.printSchema()
print(f"Particiones de lectura: {ventas.rdd.getNumPartitions()}") #rdd permite convertir el DataFrame en un RDD para acceder a sus particiones

print("Paso 1: filtrar")

# TODO 1: quedate solo con las ventas de la categoria electronica.
electronica = ventas.filter(F.col("categoria") == "electronica") #esto es lazy 
print(f"Ventas de electronica: {electronica.count()}") #para spark cuando hacemos count es trigger

print()
print("Paso 2: una columna calculada")
# TODO 2: agrega la columna monto = cantidad * precio_unitario.
con_monto = electronica.withColumn("monto", F.col("cantidad") * F.col("precio_unitario")) #con withColumn agregamos una nueva columna y con F.col referenciamos las columnas
con_monto.show(3)

print()
print("Paso 3: agregar por categoria")
# TODO 3: numero de ventas y monto total por categoria, del monto mas
# alto al mas bajo.
resumen = (
    con_monto
    .groupBy("categoria")
    .agg(                                                #con_monto.groupBy agrupamos por categoria
        F.count("*").alias("numero_ventas"),
        F.sum("monto").alias("monto_total"),
    )
    .orderBy(F.desc("monto_total"))
)
resumen.show()

print()
print("Paso 4: guardar el resultado")
# TODO 4: guarda resumen como CSV con encabezado en la carpeta
# resumen_por_categoria, reemplazandola si ya existe.

resumen.write.mode("overwrite").option("header", True).csv("resumen_por_categoria")  # el resumen.write.mode("overwrite") reemplaza el directorio si ya existe

if os.path.exists("resumen_por_categoria"):
    print("Contenido de resumen_por_categoria/:", sorted(os.listdir("resumen_por_categoria")))
else:
    print("Todavia no existe resumen_por_categoria/")

spark.stop()
