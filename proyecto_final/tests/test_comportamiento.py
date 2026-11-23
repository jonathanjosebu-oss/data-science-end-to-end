"""Comportamiento que el modelo debe cumplir en cromatografía de fase reversa (C18).

1. Flujo: con la misma molécula, columna y fase móvil, aumentar el flujo no
   debe aumentar el tiempo de retención (el analito recorre la columna antes).
2. Series homólogas: agregar un CH2 a una cadena alquílica aumenta la
   lipofilia; en fase reversa el homólogo más largo no debe eluir antes.
3. Lipofilia: dentro de la misma condición, una molécula claramente más
   lipofílica (ΔLogP > 2) no debe predecirse, en promedio, antes que una polar.

DEFECTO CONOCIDO del champion v1: incumple 1 y 2. El flujo funciona como proxy
del método (SMRT usa 0,1 mL/min; los métodos con 1,0 tienen gradientes largos)
porque la OBT no incluye el programa de gradiente. Restringir la monotonía
corrige el flujo pero sube el error en lotes nuevos un 23 % y no corrige las
series homólogas (ver src/reentrenar.py y docs/cambios.md). Ambas pruebas se
marcan xfail(strict=True): CI no se bloquea por un defecto documentado, pero
si un modelo futuro las cumple, la prueba falla para obligar a quitar la marca.
Cumplirlas es criterio de preferencia en la promoción de un challenger.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.pipeline import model_inputs

COLUMNA = "Waters ACQUITY UPLC BEH C18"
FASES = (
    "A[H2O=100; MeOH=0; ACN=0] B[H2O=0; MeOH=0; ACN=100]",
    "A[H2O=100; MeOH=0; ACN=0] B[H2O=0; MeOH=100; ACN=0]",
)
SERIES_HOMOLOGAS = {
    "alquilbencenos": ["c1ccccc1", "Cc1ccccc1", "CCc1ccccc1", "CCCc1ccccc1", "CCCCc1ccccc1", "CCCCCc1ccccc1"],
    "acidos_grasos": ["CCCCC(=O)O", "CCCCCCC(=O)O", "CCCCCCCCC(=O)O", "CCCCCCCCCCC(=O)O"],
    "alcoholes": ["CCCCO", "CCCCCCO", "CCCCCCCCO", "CCCCCCCCCCO"],
    "parabenos": ["COC(=O)c1ccc(O)cc1", "CCOC(=O)c1ccc(O)cc1", "CCCOC(=O)c1ccc(O)cc1", "CCCCOC(=O)c1ccc(O)cc1"],
}
TOL = 1e-9
DEFECTO_FLUJO = pytest.mark.xfail(
    strict=True,
    reason="Defecto conocido v1: el flujo actúa como proxy del método (falta el gradiente)",
)


@DEFECTO_FLUJO
def test_mas_flujo_no_aumenta_la_retencion(modelo, muestra_fija):
    X = model_inputs(muestra_fija)[0]
    flujos = [0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0]
    pred = np.vstack([modelo.predict(X.assign(flujo_ml_min=f)) for f in flujos])
    aumentos = np.diff(pred, axis=0) > TOL
    assert not aumentos.any(), (
        f"{aumentos.any(axis=0).mean():.1%} de los compuestos retienen más al subir el flujo"
    )


@pytest.mark.xfail(
    strict=True,
    reason="Defecto conocido v1: caídas en series homólogas (descriptores sin restricción)",
)
def test_homologo_mas_largo_no_eluye_antes(modelo):
    violaciones = []
    for serie, smiles in sorted(SERIES_HOMOLOGAS.items()):
        for fase in FASES:
            for flujo in (0.1, 0.3, 0.5):
                X = pd.DataFrame(
                    {"smiles": smiles, "tipo_columna": COLUMNA, "fase_movil": fase, "flujo_ml_min": flujo}
                )
                pred = modelo.predict(X)
                if (np.diff(pred) < -TOL).any():
                    violaciones.append(f"{serie} | {fase[-14:]} | flujo {flujo}: {np.round(pred, 2)}")
    assert not violaciones, f"{len(violaciones)} de 24 casos violan la regla:\n" + "\n".join(violaciones)


def test_moleculas_lipofilicas_retienen_mas_que_las_polares(modelo):
    polares = ["OCC(O)CO", "NCC(=O)O", "OC(=O)CC(O)(CC(=O)O)C(=O)O", "C(C1C(C(C(C(O1)O)O)O)O)O"]
    lipofilicas = ["CCCCCCCCCCCC", "c1ccc2cc3ccccc3cc2c1", "CCCCCCCCc1ccccc1", "Clc1ccc(cc1)C(c1ccc(Cl)cc1)C(Cl)(Cl)Cl"]
    for fase in FASES:
        X = lambda s: pd.DataFrame({"smiles": s, "tipo_columna": COLUMNA, "fase_movil": fase, "flujo_ml_min": 0.3})
        assert modelo.predict(X(lipofilicas)).mean() > modelo.predict(X(polares)).mean()
