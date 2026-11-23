"""El modelo exportado reproduce la métrica registrada en MLflow en la muestra fija.

Tolerancia: 1e-3 min (0,06 s). El modelo es determinista (semilla fija y las
mismas versiones de librerías), así que en la misma plataforma la diferencia
es 0; la tolerancia solo absorbe diferencias de punto flotante entre sistemas
operativos (CI corre en Linux, el registro se hizo en Windows). Es unas 50
veces menor que la desviación entre pliegues de la CV (0,054 min): cualquier
cambio real del modelo o de la preparación la supera.
"""

from __future__ import annotations

import numpy as np

from src.pipeline import model_inputs
from src.reentrenar import regression_metrics

TOLERANCIA_MIN = 1e-3


def test_reproduce_rmse_y_mae_registrados(modelo, muestra_fija, metadata_modelo):
    X, y, _ = model_inputs(muestra_fija)
    metricas = regression_metrics(y, modelo.predict(X))
    assert abs(metricas["rmse"] - metadata_modelo["muestra_fija_rmse"]) <= TOLERANCIA_MIN
    assert abs(metricas["mae"] - metadata_modelo["muestra_fija_mae"]) <= TOLERANCIA_MIN


def test_supera_a_la_linea_base_en_la_muestra_fija(modelo, muestra_fija):
    import json

    from tests.conftest import FIXTURES
    from src.reentrenar import baseline_predict

    X, y, _ = model_inputs(muestra_fija)
    linea_base = json.loads((FIXTURES / "linea_base.json").read_text(encoding="utf-8"))
    rmse_modelo = regression_metrics(y, modelo.predict(X))["rmse"]
    rmse_base = regression_metrics(y, baseline_predict(linea_base, X))["rmse"]
    assert rmse_modelo < rmse_base


def test_predicciones_finitas_y_positivas(modelo, muestra_fija):
    pred = modelo.predict(model_inputs(muestra_fija)[0])
    assert np.isfinite(pred).all()
    assert (pred > 0).mean() > 0.99
