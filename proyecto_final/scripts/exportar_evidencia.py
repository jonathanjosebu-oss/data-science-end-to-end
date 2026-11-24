"""Exporta la evidencia del PSet 4 a docs/ (formato CSV).

    python -m scripts.exportar_evidencia

docs/predicciones.csv      PRODUCCION.PREDICCIONES (versión y run_id por fila)
docs/monitoreo.csv         PRODUCCION.MONITOREO
docs/alertas.csv           PRODUCCION.ALERTAS
docs/solicitudes.csv       PRODUCCION.SOLICITUDES (métricas de sistema por llamada)
docs/corridas.csv          mlflow.search_runs: todas las corridas, incluidas las de reentrenamiento
docs/reentrenamientos.csv  corridas con tags.fase = 'reentrenamiento', unidas a la decisión
                           challenger/champion de PRODUCCION.REENTRENAMIENTOS

El tablero (tablero/app.py) lee estos CSV cuando no hay acceso a Snowflake.
"""

from __future__ import annotations

from pathlib import Path

import mlflow
import pandas as pd

from src import almacen
from src.experiments import EXPERIMENT_NAME, configure_tracking

DOCS = Path(__file__).resolve().parents[1] / "docs"
TABLAS = {
    "predicciones": "SELECT * FROM PREDICCIONES ORDER BY LOTE, TS, HECHO_ID",
    "monitoreo": "SELECT * FROM MONITOREO ORDER BY LOTE, TIPO, METRICA, FEATURE",
    "alertas": "SELECT * FROM ALERTAS ORDER BY LOTE, ALERTA",
    "solicitudes": "SELECT * FROM SOLICITUDES ORDER BY LOTE, TS",
}


def exportar() -> dict[str, int]:
    DOCS.mkdir(exist_ok=True)
    filas = {}
    for nombre, sql in TABLAS.items():
        frame = almacen.consultar(sql)
        frame.to_csv(DOCS / f"{nombre}.csv", index=False)
        filas[nombre] = len(frame)

    configure_tracking()
    corridas = mlflow.search_runs(experiment_names=[EXPERIMENT_NAME], order_by=["attributes.start_time ASC"])
    corridas.to_csv(DOCS / "corridas.csv", index=False)
    filas["corridas"] = len(corridas)

    reent = corridas.loc[corridas.get("tags.fase", pd.Series(dtype=str)).eq("reentrenamiento")].copy()
    decisiones = almacen.consultar("SELECT * FROM REENTRENAMIENTOS ORDER BY LOTE")
    reent = reent.merge(decisiones, on="run_id", how="left")
    reent.to_csv(DOCS / "reentrenamientos.csv", index=False)
    filas["reentrenamientos"] = len(reent)
    # Tabla de decisiones sola: la lee el tablero sin depender de MLflow.
    decisiones.to_csv(DOCS / "reentrenamientos_decisiones.csv", index=False)
    return filas


if __name__ == "__main__":
    for nombre, n in exportar().items():
        print(f"docs/{nombre}.csv: {n} filas")
