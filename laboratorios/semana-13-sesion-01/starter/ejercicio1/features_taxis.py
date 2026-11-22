"""Las features de tiempo y de tarifa fija de los viajes, como funcion.

Son las mismas que se calcularon para construir viajes_features.csv (Semana 9):
la app solo conoce la fecha y hora, las zonas, la distancia, los pasajeros y
el metodo de pago, y el servicio calcula el resto con esta funcion.

    from features_taxis import agregar_features

No lo modifiques: si el servicio calcula una feature distinta de la que vio
el modelo al entrenar, el modelo se equivoca sin dar ningun error.
"""

import numpy as np
import pandas as pd

ZONAS_MANHATTAN = ["Midtown", "Upper East Side", "Upper West Side", "Lower Manhattan", "Harlem"]


def agregar_features(viajes):
    """Devuelve una copia de los viajes con hora_sin, hora_cos,
    es_fin_de_semana, es_hora_pico y es_tarifa_fija."""
    viajes = viajes.copy()
    inicio = pd.to_datetime(viajes["fecha_hora_inicio"])
    hora = inicio.dt.hour
    viajes["hora_sin"] = np.sin(2 * np.pi * hora / 24).round(4)
    viajes["hora_cos"] = np.cos(2 * np.pi * hora / 24).round(4)
    viajes["es_fin_de_semana"] = (inicio.dt.dayofweek >= 5).astype(int)
    viajes["es_hora_pico"] = (hora.isin([7, 8, 9, 16, 17, 18, 19]) & (viajes["es_fin_de_semana"] == 0)).astype(int)
    jfk_a_manhattan = (viajes["zona_origen"] == "JFK Airport") & viajes["zona_destino"].isin(ZONAS_MANHATTAN)
    manhattan_a_jfk = viajes["zona_origen"].isin(ZONAS_MANHATTAN) & (viajes["zona_destino"] == "JFK Airport")
    viajes["es_tarifa_fija"] = (jfk_a_manhattan | manhattan_a_jfk).astype(int)
    return viajes
