"""Ejercicio 2: el monitoreo del servicio de fraude.

El servicio de fraude (version 2, el gradient boosting) guarda cada pago que
evalua en predicciones_fraude.csv: cuando llego, la probabilidad, si lo mando
a revision y cuanto tardo en responder. Los fraudes no se conocen en el
momento: se confirman cuando el titular de la tarjeta reclama el cobro (un
contracargo), entre 2 y 21 dias despues, y quedan en contracargos.csv.

Hoy es 14 de diciembre. El reporte separa las metricas del sistema (la
latencia), una metrica que se puede calcular el mismo dia (la tasa de
alertas) y la metrica del modelo que le importa al negocio (el recall), que
solo se puede calcular para las semanas cuyos fraudes ya se confirmaron.

    python monitoreo_fraude.py

Despues de resolver, corre python comprobar.py hasta que los cinco pasos
digan OK.
"""

import pandas as pd

HOY = "2026-12-14"
DEMORA_MAXIMA = 21          # dias que puede tardar en confirmarse un fraude
TASA_REFERENCIA = 0.0758    # pagos enviados a revision en la prueba, con el umbral 0.10
RECALL_REFERENCIA = 0.661   # recall en la prueba, con el umbral 0.10
LATENCIA_MAXIMA_MS = 50


def con_dia_y_semana(predicciones):
    """Agrega "dia" (la fecha) y "semana" (el lunes de la semana) a cada pago."""
    predicciones = predicciones.copy()
    fecha = pd.to_datetime(predicciones["fecha_hora"])
    predicciones["dia"] = fecha.dt.date
    predicciones["semana"] = fecha.dt.to_period("W").dt.start_time.dt.date
    return predicciones


def latencia_p95(predicciones):
    """La latencia p95 de cada dia, en milisegundos: una Series indexada por dia."""
    # TODO 1: agrupa por "dia" y calcula el cuantil 0.95 de "latencia_ms"
    # (.quantile(0.95)).
    return pd.Series(dtype=float)


def tasa_de_alertas(predicciones):
    """La fraccion de pagos enviados a revision en cada semana: una Series
    indexada por semana."""
    # TODO 2: agrupa por "semana" y promedia la columna "revisar" (vale 1 o 0).
    return pd.Series(dtype=float)


def fraudes_confirmados(contracargos, hoy):
    """Los id_pago de los fraudes confirmados hasta hoy (incluido), como set."""
    # TODO 3: filtra los contracargos con fecha_confirmacion menor o igual a
    # hoy (las fechas son texto "AAAA-MM-DD", y se comparan bien como texto).
    return set()


def recall_por_semana(predicciones, contracargos, hoy):
    """El recall de cada semana cuyos fraudes ya se confirmaron todos: una
    semana entra si su domingo, mas DEMORA_MAXIMA dias, es menor o igual a
    hoy. Devuelve un DataFrame indexado por semana, con las columnas
    "fraudes", "detectados" y "recall"."""
    # Marca como fraude los pagos que estan en fraudes_confirmados(...), deja
    # solo las semanas maduras, y por semana cuenta los fraudes, los fraudes
    # con revisar == 1, y su cociente.
    return pd.DataFrame(columns=["fraudes", "detectados", "recall"])


def alertas(predicciones, contracargos, hoy):
    """Una lista de mensajes, uno por cada problema encontrado."""
    mensajes = []
    # Tres tipos de alerta, en este orden:
    # - "sistema: el <dia> la latencia p95 fue <x> ms", por cada dia con
    #   latencia p95 mayor que LATENCIA_MAXIMA_MS;
    # - "modelo (indirecta): la semana del <semana> mando a revision <x> de los pagos",
    #   por cada semana con una tasa de alertas menor que el 75% de TASA_REFERENCIA;
    # - "modelo: la semana del <semana> detecto <x> de los fraudes", por cada
    #   semana madura con recall menor que el 75% de RECALL_REFERENCIA.
    # Usa las funciones de arriba, y redondea x a 3 decimales (1 en la latencia).
    return mensajes


if __name__ == "__main__":
    predicciones = con_dia_y_semana(pd.read_csv("predicciones_fraude.csv"))
    contracargos = pd.read_csv("contracargos.csv")
    print(f"{len(predicciones)} pagos evaluados del {predicciones['dia'].min()} al {predicciones['dia'].max()}")
    print("\nLatencia p95 por dia (ms), los cinco dias mas lentos:")
    print(latencia_p95(predicciones).sort_values(ascending=False).head(5).round(1).to_string())
    print("\nTasa de alertas por semana:")
    print(tasa_de_alertas(predicciones).round(4).to_string())
    print(f"\nRecall por semana madura, al {HOY}:")
    print(recall_por_semana(predicciones, contracargos, HOY).to_string())
    print("\nAlertas:")
    for mensaje in alertas(predicciones, contracargos, HOY):
        print("-", mensaje)
