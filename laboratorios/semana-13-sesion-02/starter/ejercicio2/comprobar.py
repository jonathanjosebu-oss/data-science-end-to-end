"""Comprobacion del Ejercicio 2. Correla desde esta carpeta:

    python comprobar.py

Prueba cada funcion de monitoreo_fraude.py con unos pocos pagos inventados,
cuyo resultado se conoce. Imprime OK o revisa por cada paso. No la modifiques.
"""

import pandas as pd

import monitoreo_fraude as m


def comprobar(numero, condicion):
    if condicion:
        print(f"Paso {numero}: OK")
    else:
        print(f"Paso {numero}: revisa")


def intentar(funcion, *argumentos):
    try:
        return funcion(*argumentos)
    except Exception:
        return None


# Dos semanas: la del 2 de noviembre (4 pagos) y la del 9 (4 pagos).
pagos = m.con_dia_y_semana(pd.DataFrame({
    "id_pago": ["a", "b", "c", "d", "e", "f", "g", "h"],
    "fecha_hora": ["2026-11-02 10:00", "2026-11-02 11:00", "2026-11-03 09:00", "2026-11-03 12:00",
                   "2026-11-09 10:00", "2026-11-09 11:00", "2026-11-10 09:00", "2026-11-10 12:00"],
    "revisar": [1, 0, 1, 0, 0, 0, 0, 1],
    "latencia_ms": [2.0, 4.0, 3.0, 300.0, 2.0, 2.0, 2.0, 2.0],
}))
contracargos = pd.DataFrame({"id_pago": ["a", "b", "d", "e", "g"],
                             "fecha_confirmacion": ["2026-11-05", "2026-11-20", "2026-11-25", "2026-11-12", "2026-12-20"]})

latencias = intentar(m.latencia_p95, pagos)
paso_1 = (latencias is not None and len(latencias) == 4
          and abs(latencias[pd.Timestamp("2026-11-03").date()] - 285.15) < 0.01
          and abs(latencias[pd.Timestamp("2026-11-02").date()] - 3.9) < 0.01)

tasas = intentar(m.tasa_de_alertas, pagos)
paso_2 = tasas is not None and len(tasas) == 2 and list(tasas.round(2)) == [0.5, 0.25]

paso_3 = (intentar(m.fraudes_confirmados, contracargos, "2026-11-12") == {"a", "e"}
          and intentar(m.fraudes_confirmados, contracargos, "2026-12-31") == {"a", "b", "d", "e", "g"})

# Al 1 de diciembre solo esta madura la semana del 2 (domingo 8, mas 21 dias).
tabla = intentar(m.recall_por_semana, pagos, contracargos, "2026-12-01")
paso_4 = (tabla is not None and len(tabla) == 1
          and tabla.iloc[0]["fraudes"] == 3 and tabla.iloc[0]["detectados"] == 1 and tabla.iloc[0]["recall"] == 0.333)

mensajes = intentar(m.alertas, pagos, contracargos, "2026-12-01") or []
paso_5 = (len(mensajes) == 2 and mensajes[0].startswith("sistema: el 2026-11-03")
          and mensajes[1].startswith("modelo: la semana del 2026-11-02"))

comprobar(1, paso_1)
comprobar(2, paso_2)
comprobar(3, paso_3)
comprobar(4, paso_4)
comprobar(5, paso_5)
