import os
from dotenv import load_dotenv
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

load_dotenv()

# Si ya descargaste o tienes el archivo a mano en la carpeta, búscalo directamente:
# O pon la ruta exacta si está en otra carpeta, ej: "kestra/report.csv"
local_path = "report.csv"

if os.path.exists(local_path):
    print(f"Cargando el archivo local '{local_path}'...")
    df = pd.read_csv(local_path, low_memory=False)
else:
    # Si prefieres descargarlo, coloca el archivo manualmente en la carpeta psets/pset-02/ con el nombre report.csv
    raise FileNotFoundError(
        "Coloca el archivo 'report.csv' en la carpeta actual para proceder con la carga a Snowflake.")

print(f"¡Datos listos en memoria! Total de filas: {len(df)}")

print("Conectando a Snowflake...")
conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    role=os.getenv("SNOWFLAKE_ROLE"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    schema=os.getenv("SNOWFLAKE_SCHEMA")
)

print("Cargando datos en la tabla RAW_REPORT_DATA de Snowflake...")
success, nchunks, nrows, _ = write_pandas(
    conn, df, "RAW_REPORT_DATA", quote_identifiers=False)
print(f"¡Carga exitosa! Filas insertadas: {nrows}")

conn.close()
