"""Comprobacion del Ejercicio 2. Correla desde esta carpeta:

    python comprobar.py

Prueba cada pieza de deriva.py con datos inventados cuyo resultado se
conoce. Imprime OK o revisa por cada paso. No la modifiques.
"""

import numpy as np

import deriva


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


def cerca(a, b):
    return a is not None and len(a) == len(b) and np.allclose(a, b)


p1 = intentar(deriva.proporciones_numericas, [1.0, 2.0, None, 5.0, 9.0], [3.0, 6.0])
comprobar(1, cerca(p1, [0.5, 0.25, 0.25]) and cerca(intentar(deriva.proporciones_numericas, [None], [3.0]), [0.0, 0.0]))

p2 = intentar(deriva.proporciones_categoricas, ["a", "b", "a", "z"], ["a", "b", "c"])
comprobar(2, cerca(p2, [0.5, 0.25, 0.0]))

igual = intentar(deriva.psi, [0.5, 0.5], [0.5, 0.5])
distinto = intentar(deriva.psi, [0.5, 0.5], [0.9, 0.1])
vacia = intentar(deriva.psi, [0.5, 0.5], [1.0, 0.0])
comprobar(3, igual == 0.0 and distinto is not None and abs(distinto - 0.8789) < 0.001
          and vacia is not None and abs(vacia - 4.6043) < 0.001)

referencia = {"distancia_km": {"cortes": [5.0], "proporciones": [0.5, 0.5]},
              "zona_origen": {"categorias": ["A", "B"], "proporciones": [0.5, 0.5]}}
monitor = deriva.MonitorDeDeriva(referencia, ventana=4, umbral=0.15)
for distancia, zona in [(1.0, "A"), (9.0, "B"), (2.0, "A"), (8.0, "B"), (1.0, "A"), (9.0, "B")]:
    intentar(monitor.registrar, {"distancia_km": distancia, "zona_origen": zona})
comprobar(4, monitor.distancias == [2.0, 8.0, 1.0, 9.0] and monitor.zonas == ["A", "B", "A", "B"])

e1 = intentar(monitor.estado)
corto = deriva.MonitorDeDeriva(referencia, ventana=4, umbral=0.15)
for distancia, zona in [(1.0, "A"), (1.0, "A")]:
    intentar(corto.registrar, {"distancia_km": distancia, "zona_origen": zona})
e2 = intentar(corto.estado)
sesgado = deriva.MonitorDeDeriva(referencia, ventana=4, umbral=0.15)
for distancia, zona in [(1.0, "A"), (1.0, "A"), (2.0, "A"), (9.0, "A")]:
    intentar(sesgado.registrar, {"distancia_km": distancia, "zona_origen": zona})
e3 = intentar(sesgado.estado)
e4 = intentar(deriva.MonitorDeDeriva(referencia, ventana=4, umbral=0.15).estado)
comprobar(5, e1 == {"viajes_en_ventana": 4, "psi": {"distancia_km": 0.0, "zona_origen": 0.0}, "alerta": False}
          and e2 is not None and e2["alerta"] is False and e2["viajes_en_ventana"] == 2
          and e3 is not None and e3["alerta"] is True and e3["psi"]["zona_origen"] > 0.15
          and e4 == {"viajes_en_ventana": 0, "psi": {}, "alerta": False})
