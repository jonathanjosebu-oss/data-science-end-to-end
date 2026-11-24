"""Simulación de producción (PSet 4 §5).

Línea de tiempo: el lote k es la semana k a partir del corte (experimento 0275).
En la semana k el laboratorio diseña los métodos del lote k y pide
predicciones a la API; los tiempos de retención reales de ese lote llegan
**una semana después** (horizonte: el analista inyecta y reporta), así que el
desempeño del lote k se calcula en la semana k+1. Por eso hay 11 semanas para
10 lotes.

Deriva inducida (documentada en docs/simulacion.md): desde el lote 06 el
laboratorio transfiere sus métodos de un UHPLC (volumen de retardo ~0,1 mL) a
un HPLC convencional (~1,1 mL): 1,0 mL más de volumen de retardo (dwell
volume). El gradiente llega a la columna 1,0/F min más tarde, así que cada
tiempo de retención real se retrasa 1,0/F min. Las entradas que ve el modelo
no cambian: es deriva conceptual. En los lotes 09 y 10 RepoRT no reporta
flujo; se asume F = 0,4 mL/min (mediana de los lotes con flujo).
Con 0,5 mL la deriva quedaba dentro de la variación natural entre métodos
(lote 06: sesgo -1,05 min frente a un umbral calibrado de 1,81) y no se
distinguía de la degradación natural del lote 08.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from src.pipeline import RAW_FEATURE_COLUMNS

INICIO_SIMULACION = date(2026, 1, 5)  # lunes de la semana 1 (fecha simulada)
DERIVA_DESDE_LOTE = 6
VOLUMEN_RETARDO_EXTRA_ML = 1.0
FLUJO_SUPUESTO_SIN_DATO = 0.4
HORIZONTE_LOTES = 1  # el target del lote k llega con el lote k+1
COLUMNAS_LOTE = ["hecho_id", "experimento_id", "inchikey", *RAW_FEATURE_COLUMNS]


def numero_lote(segmento: str) -> int:
    return int(segmento.removeprefix("lote_"))


def fecha_lote(lote: int) -> date:
    return INICIO_SIMULACION + timedelta(weeks=lote - 1)


def inducir_deriva(lote: pd.DataFrame, numero: int) -> pd.DataFrame:
    """Aplica el retraso por volumen de retardo a los lotes >= DERIVA_DESDE_LOTE."""
    lote = lote.copy()
    lote["tiempo_retencion_original"] = lote["tiempo_retencion"]
    lote["deriva_inducida"] = numero >= DERIVA_DESDE_LOTE
    if numero >= DERIVA_DESDE_LOTE:
        flujo = pd.to_numeric(lote["flujo_ml_min"], errors="coerce").fillna(FLUJO_SUPUESTO_SIN_DATO)
        lote["tiempo_retencion"] = lote["tiempo_retencion"] + VOLUMEN_RETARDO_EXTRA_ML / flujo
    return lote


def construir_lotes(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (entradas, targets) de los lotes, con la deriva ya inducida.

    `entradas` es lo que el laboratorio conoce al pedir la predicción (sin el
    target); `targets` es lo que llega después de inyectar.
    """
    lotes = frame.loc[frame["segment"].str.startswith("lote_")].copy()
    partes = []
    for segmento, grupo in lotes.groupby("segment", sort=True):
        numero = numero_lote(segmento)
        partes.append(inducir_deriva(grupo, numero).assign(lote=numero))
    lotes = pd.concat(partes, ignore_index=True)
    lotes["semana_prediccion"] = lotes["lote"].map(fecha_lote)
    lotes["semana_llegada_target"] = (lotes["lote"] + HORIZONTE_LOTES).map(fecha_lote)
    entradas = lotes.loc[:, ["lote", "semana_prediccion", *COLUMNAS_LOTE]]
    targets = lotes.loc[
        :,
        [
            "lote", "semana_llegada_target", "hecho_id", "tiempo_retencion",
            "tiempo_retencion_original", "deriva_inducida",
        ],
    ]
    return entradas, targets


def solicitudes_de_lote(entradas: pd.DataFrame, max_compuestos: int = 50) -> list[dict[str, Any]]:
    """Agrupa un lote en solicitudes a la API: un método (experimento) y hasta
    `max_compuestos` analitos por solicitud, como los enviaría el analista."""
    solicitudes = []
    for _, metodo in entradas.groupby("experimento_id", sort=True):
        primera = metodo.iloc[0]
        base = {
            "tipo_columna": primera["tipo_columna"],
            "fase_movil": primera["fase_movil"],
            "flujo_ml_min": _o_none(primera["flujo_ml_min"]),
            "t0_min": _o_none(primera["t0_min"]),
            "columna_longitud_mm": _o_none(primera["columna_longitud_mm"]),
            "columna_diametro_mm": _o_none(primera["columna_diametro_mm"]),
            "columna_particula_um": _o_none(primera["columna_particula_um"]),
            "ph_a": _o_none(primera["ph_a"]),
            "ph_b": _o_none(primera["ph_b"]),
            "gradiente": _gradiente_api(primera["gradiente"]),
            "lote": f"lote_{int(primera['lote']):02d}",
        }
        for inicio in range(0, len(metodo), max_compuestos):
            trozo = metodo.iloc[inicio : inicio + max_compuestos]
            solicitudes.append(
                {
                    **base,
                    "compuestos": [
                        {"id": str(r.hecho_id), "smiles": str(r.smiles)} for r in trozo.itertuples()
                    ],
                }
            )
    return solicitudes


def _o_none(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(numero) else numero


def _gradiente_api(valor: Any) -> list[dict[str, float]] | None:
    """Programa de la OBT -> pasos de la API. Los pasos que la API rechazaría
    (suma de % distinta de 100 o tiempos que retroceden) dejan el gradiente
    como no reportado, igual que haría un analista con un dato incompleto."""
    from src.pipeline import parse_gradient

    pasos = []
    for t, a, b, c, d, flujo in parse_gradient(valor):
        a, b, c, d = (0.0 if v is None else v for v in (a, b, c, d))
        if abs(a + b + c + d - 100) > 1:
            return None
        paso = {"t_min": t, "a_pct": a, "b_pct": b, "c_pct": c, "d_pct": d}
        if flujo is not None and 0 < flujo <= 5:
            paso["flujo_ml_min"] = flujo
        pasos.append(paso)
    return pasos or None
