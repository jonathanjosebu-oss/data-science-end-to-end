"""Simulación (deriva inducida, horizonte, solicitudes) y monitoreo (PSI, chi², negocio)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from monitoreo.deriva import bordes_cuantiles, chi2_categorica, proporciones, psi
from src.business_metrics import corridas_evitadas
from src.simulacion import (
    DERIVA_DESDE_LOTE,
    VOLUMEN_RETARDO_EXTRA_ML,
    fecha_lote,
    inducir_deriva,
    solicitudes_de_lote,
)

FASE = "A[H2O=100; MeOH=0; ACN=0] B[H2O=0; MeOH=0; ACN=100]"


def _lote(n=6, flujo=0.5):
    return pd.DataFrame(
        {
            "hecho_id": [f"h{i}" for i in range(n)], "experimento_id": ["0300"] * n,
            "inchikey": [f"k{i}" for i in range(n)], "smiles": ["CCO"] * n,
            "tipo_columna": "X C18", "fase_movil": FASE, "flujo_ml_min": flujo,
            "t0_min": 1.0, "columna_longitud_mm": 100.0, "columna_diametro_mm": 2.1,
            "columna_particula_um": 1.7, "ph_a": 2.7, "ph_b": np.nan,
            "gradiente": "[[0,95,5,0,0,0.5],[10,5,95,0,0,0.5]]", "lote": 3,
            "tiempo_retencion": np.linspace(1, 10, n),
        }
    )


def test_deriva_solo_desde_el_lote_indicado_y_proporcional_a_1_sobre_flujo():
    antes = inducir_deriva(_lote(), DERIVA_DESDE_LOTE - 1)
    assert (antes["tiempo_retencion"] == antes["tiempo_retencion_original"]).all()
    despues = inducir_deriva(_lote(flujo=0.5), DERIVA_DESDE_LOTE)
    retraso = despues["tiempo_retencion"] - despues["tiempo_retencion_original"]
    assert np.allclose(retraso, VOLUMEN_RETARDO_EXTRA_ML / 0.5)
    assert despues["deriva_inducida"].all()


def test_el_target_llega_una_semana_despues():
    assert (fecha_lote(4) - fecha_lote(3)).days == 7


def test_solicitudes_agrupan_por_metodo_y_respetan_el_tope():
    solicitudes = solicitudes_de_lote(_lote(n=120), max_compuestos=50)
    assert [len(s["compuestos"]) for s in solicitudes] == [50, 50, 20]
    assert solicitudes[0]["gradiente"][1] == {"t_min": 10.0, "a_pct": 5.0, "b_pct": 95.0,
                                              "c_pct": 0.0, "d_pct": 0.0, "flujo_ml_min": 0.5}
    assert solicitudes[0]["ph_b"] is None


def test_psi_cero_para_la_misma_distribucion_y_alto_si_se_desplaza():
    rng = np.random.default_rng(0)
    ref = rng.normal(size=5000)
    bordes = bordes_cuantiles(ref)
    base = proporciones(ref, bordes)
    assert psi(base, proporciones(rng.normal(size=5000), bordes)) < 0.05
    assert psi(base, proporciones(rng.normal(loc=1.5, size=5000), bordes)) > 1.0


def test_chi2_detecta_categorias_no_vistas():
    p, fraccion, nuevas = chi2_categorica({"A": 0.5, "B": 0.5}, pd.Series(["A", "C", "C", "C"]))
    assert fraccion == 0.75 and nuevas == 1 and p < 0.05


def test_corridas_evitadas_es_cero_si_el_intervalo_es_ancho():
    y = np.repeat(np.arange(10.0), 3)
    grupos = np.repeat(["m1", "m2", "m3"], 10)
    r = corridas_evitadas(y, y, grupos, (-50, 50), analitos=3, metodos=200)
    assert r["tasa_aprobacion"] == 0 and r["neto"] == 0


def test_corridas_evitadas_premia_un_modelo_perfecto_con_intervalo_angosto():
    y = np.arange(0.0, 60.0, 2.0)
    grupos = np.repeat(["m1", "m2", "m3"], 10)
    r = corridas_evitadas(y, y, grupos, (-0.1, 0.1), analitos=3, metodos=200)
    assert r["neto"] == r["ahorro"] == 1.0 and r["fallo"] == 0
