"""Ejercicio 2: el reporte de fraude de noviembre, en dolares.

El reporte tecnico de la Semana 13 decia: "el recall de la semana del 16
cayo de 0.74 a 0.28". Para la gerencia, ese numero no dice nada. Este
script lo traduce: cuanto costo cada semana el fraude que no se detecto y
las revisiones de pagos legitimos, con los costos de la Semana 11 (un
fraude no detectado cuesta 40 dolares; revisar un pago legitimo, 3).

Usa las mismas predicciones y contracargos de la Semana 13, al 14 de
diciembre, y solo las semanas cuyos fraudes ya se confirmaron todos.

    python costos_fraude.py

Despues de resolver, corre python comprobar.py hasta que los cinco pasos
digan OK.
"""

import pandas as pd

HOY = "2026-12-14"
DEMORA_MAXIMA = 21
COSTO_FRAUDE_NO_DETECTADO = 40
COSTO_FALSA_ALARMA = 3


def semanas_maduras(predicciones, contracargos, hoy):
    """Los pagos de las semanas maduras, con la columna es_fraude. Dado."""
    pagos = predicciones.copy()
    fecha = pd.to_datetime(pagos["fecha_hora"])
    pagos["semana"] = fecha.dt.to_period("W").dt.start_time.dt.date
    confirmados = set(contracargos.loc[contracargos["fecha_confirmacion"] <= hoy, "id_pago"])
    pagos["es_fraude"] = pagos["id_pago"].isin(confirmados)
    domingo = pd.to_datetime(pagos["semana"]) + pd.Timedelta(days=6)
    return pagos[domingo + pd.Timedelta(days=DEMORA_MAXIMA) <= pd.Timestamp(hoy)]


def errores_por_semana(pagos):
    """Por semana: "fraudes", "no_detectados" (fraudes con revisar == 0) y
    "falsas_alarmas" (pagos legitimos con revisar == 1)."""
    # TODO 1: agrega dos columnas booleanas a una copia de pagos
    # (no_detectado y falsa_alarma) y suma por semana las tres cosas.
    return pd.DataFrame(columns=["fraudes", "no_detectados", "falsas_alarmas"])


def costo_por_semana(errores):
    """Agrega a una copia las columnas "costo_fraude", "costo_revisiones" y
    "costo_total", en dolares."""
    # TODO 2: cada columna es la cantidad por su costo; el total, la suma.
    return errores


def costo_normal(costos):
    """El costo total promedio de las semanas antes del cambio (las dos
    primeras semanas de la tabla)."""
    # TODO 3: el promedio de costo_total de las dos primeras filas.
    return 0.0


def frase_ejecutiva(costos):
    """Una oracion para la gerencia sobre la ultima semana madura."""
    # Arma la oracion: "La semana del <semana>, el fraude que no detectamos
    # y las revisiones costaron <costo> dolares, <veces> veces una semana
    # normal." con la ultima fila de costos, el costo redondeado sin
    # decimales y las veces con un decimal.
    return ""


def costo_de_un_mes_asi(costos):
    """Lo que costaria un mes (4 semanas) como la ultima semana madura,
    menos lo que costaria un mes normal: lo que esta en juego si no se hace
    nada."""
    # Cuatro veces la diferencia entre el costo total de la ultima semana y
    # el costo normal, redondeado sin decimales.
    return 0


if __name__ == "__main__":
    predicciones = pd.read_csv("predicciones_fraude.csv")
    contracargos = pd.read_csv("contracargos.csv")
    costos = costo_por_semana(errores_por_semana(semanas_maduras(predicciones, contracargos, HOY)))
    print(costos.to_string())
    print()
    print("Costo de una semana normal:", round(costo_normal(costos)), "dolares")
    print(frase_ejecutiva(costos))
    print("Un mes asi, comparado con uno normal:", costo_de_un_mes_asi(costos), "dolares mas")
