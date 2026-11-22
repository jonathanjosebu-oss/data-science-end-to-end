FROM apache/spark:3.5.3

# El conector de Snowflake y su driver JDBC se resuelven al construir la imagen
# y quedan en el classpath de Spark: el job no descarga nada en tiempo de
# ejecución, así Kestra puede lanzar la imagen sin red hacia Maven Central.
ARG SNOWFLAKE_SPARK_PACKAGE=net.snowflake:spark-snowflake_2.12:3.2.3-spark_3.5
USER root
RUN echo "" > /tmp/noop.py \
    && /opt/spark/bin/spark-submit \
         --conf spark.jars.ivy=/tmp/ivy \
         --packages "${SNOWFLAKE_SPARK_PACKAGE}" /tmp/noop.py \
    && cp /tmp/ivy/jars/*.jar /opt/spark/jars/ \
    && rm -rf /tmp/ivy /tmp/noop.py
COPY obt_processing.py /opt/pset2/spark/obt_processing.py
USER spark
WORKDIR /opt/pset2
