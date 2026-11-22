"""Ejercicio 1: los resultados de noviembre, para dos audiencias.

tarifas_noviembre.csv tiene los 1156 viajes de noviembre del monitoreo de
la Semana 13: la tarifa que estimo la version 1 del modelo, la que se
cobro, y si el viaje tenia tarifa fija. Este script calcula el resumen por
semana y dibuja dos graficos con los mismos datos: uno para el equipo de
datos (grafico_tecnico.png) y otro para la gerencia (grafico_ejecutivo.png).

    python graficos_tarifa.py
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

MAE_PRUEBA = 1.17

viajes = pd.read_csv("tarifas_noviembre.csv")
viajes["semana"] = pd.to_datetime(viajes["fecha_hora_inicio"]).dt.to_period("W").dt.start_time.dt.strftime("%d/%m")
viajes["error"] = (viajes["tarifa_cobrada"] - viajes["tarifa_estimada"]).abs()
viajes["diferencia"] = viajes["tarifa_cobrada"] - viajes["tarifa_estimada"]

# TODO 1: el resumen por semana: "viajes" (cuantos), "mae" (promedio de
# error), "pagan_20_mas" (fraccion de viajes en que la tarifa cobrada
# supera en mas de 20% a la estimada) y "diferencia" (promedio de
# diferencia, en dolares). Redondea a 3 decimales.
resumen = pd.DataFrame(columns=["viajes", "mae", "pagan_20_mas", "diferencia"])
print(resumen.to_string())

# El grafico tecnico: el MAE por semana, separado por tipo de tarifa, con
# el MAE de prueba como referencia.
por_tipo = viajes.groupby(["semana", "es_tarifa_fija"])["error"].mean().unstack()
por_tipo.columns = ["Taximetro", "Tarifa fija"]
figura, eje = plt.subplots(figsize=(7, 4))
# TODO 2: barras agrupadas con por_tipo.plot(kind="bar", ax=eje), una linea
# horizontal en MAE_PRUEBA (eje.axhline, punteada, con label), la
# leyenda, y titulo y ejes que digan que se mide y en que unidad.
figura.tight_layout()
figura.savefig("grafico_tecnico.png", dpi=150)

# El grafico ejecutivo: una sola serie, con el mensaje en el titulo.
figura, eje = plt.subplots(figsize=(7, 4))
# TODO 3: una barra por semana con el porcentaje de pasajeros que pagaron mas
# de 20% sobre lo estimado (resumen["pagan_20_mas"] * 100), las dos
# ultimas semanas de otro color, el valor encima de cada barra, y un
# titulo que diga la conclusion, no la metrica.
figura.tight_layout()
figura.savefig("grafico_ejecutivo.png", dpi=150)
print("Graficos guardados: grafico_tecnico.png y grafico_ejecutivo.png")
