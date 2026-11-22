from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# TODO: reemplaza "mi-job-spark" por un nombre propio de tu proyecto.
spark = SparkSession.builder.appName("mi-job-spark").master("local[*]").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

# TODO: reemplaza por la ruta real del archivo historico de tu proyecto
# (el mismo que tu pipeline orquestado de la Semana 4 genera o acumula).
historico = spark.read.csv("../data/raw/TODO_archivo.csv", header=True, inferSchema=True)
print(f"Particiones de lectura: {historico.rdd.getNumPartitions()}")
print(f"Filas leidas: {historico.count()}")

# TODO: reescribe aqui, con la API de Spark, la misma transformacion de pandas
# que ya usaste en una sesion anterior (por ejemplo, una columna calculada con
# withColumn y una agregacion con groupBy().agg()).
resultado = (
    historico
    # .withColumn("TODO_columna_calculada", F.col("TODO") * TODO)
    .groupBy("TODO_columna_categorica")
    .agg(
        F.count("*").alias("TODO_alias_conteo"),
        # F.avg("TODO_columna_numerica").alias("TODO_alias_promedio"),
    )
    .orderBy(F.desc("TODO_alias_conteo"))
)
resultado.show()

# TODO: guarda el resultado como salida del job.
resultado.write.mode("overwrite").csv("TODO_carpeta_resultado", header=True)

spark.stop()
