"""Comprobacion del Ejercicio 2. Correla desde esta carpeta:

    python comprobar.py

Prueba cada funcion de costos_fraude.py con pocos pagos inventados.
Imprime OK o revisa por cada paso. No la modifiques.
"""

import pandas as pd

import costos_fraude as c


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


pagos = pd.DataFrame({
    "semana": ["s1", "s1", "s1", "s1", "s2", "s2", "s2", "s3", "s3", "s3"],
    "es_fraude": [True, True, False, False, True, False, False, True, True, False],
    "revisar": [1, 0, 1, 0, 0, 1, 1, 0, 0, 0],
})
errores = intentar(c.errores_por_semana, pagos)
paso_1 = (errores is not None and len(errores) == 3
          and list(errores["fraudes"]) == [2, 1, 2]
          and list(errores["no_detectados"]) == [1, 1, 2]
          and list(errores["falsas_alarmas"]) == [1, 2, 0])
comprobar(1, paso_1)

base = pd.DataFrame({"fraudes": [2, 1, 2], "no_detectados": [1, 1, 2], "falsas_alarmas": [1, 2, 0]}, index=["s1", "s2", "s3"])
costos = intentar(c.costo_por_semana, base)
paso_2 = (costos is not None and "costo_total" in costos
          and list(costos["costo_fraude"]) == [40, 40, 80]
          and list(costos["costo_revisiones"]) == [3, 6, 0]
          and list(costos["costo_total"]) == [43, 46, 80])
comprobar(2, paso_2)

ejemplo = pd.DataFrame({"costo_total": [43, 46, 80]}, index=["s1", "s2", "s3"])
comprobar(3, intentar(c.costo_normal, ejemplo) == 44.5)

frase = intentar(c.frase_ejecutiva, ejemplo)
comprobar(4, frase == "La semana del s3, el fraude que no detectamos y las revisiones costaron 80 dolares, 1.8 veces una semana normal.")

comprobar(5, intentar(c.costo_de_un_mes_asi, ejemplo) == 142)
