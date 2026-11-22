# PSet 3: Rúbrica de evaluación

> PSet 3 es uno de los 4 PSets del curso, que en conjunto valen 25% de la nota final. Los 4 PSets pesan igual entre sí (6.25% cada uno de la nota total), salvo que yo decida una ponderación distinta.

Cada criterio se califica en una escala de 0 a 4; la nota final del PSet es el promedio de los cinco.

## 1. Exploración y features

| Nivel | Descripción |
|---|---|
| 4, Excelente | La exploración resume el dataset (filas, columnas, faltantes por columna), describe la distribución del objetivo y sus atípicos, y muestra la relación entre el objetivo y la variable que se espera que más influya. Los tres hallazgos tienen la celda con el número o el gráfico que los confirma y, debajo, qué cambia en el modelo por su causa. El notebook de features dice qué predice el modelo y en qué momento; las dos features tienen evidencia de que aportan, al menos una sale de un hallazgo, y cada justificación dice por qué existe en el momento de predecir y, si es categórica, qué codificación usaría. |
| 3, Logrado | Hallazgos y features tienen evidencia, pero algún hallazgo no dice qué cambia en el modelo o alguna feature no justifica el momento de predicción. |
| 2, En desarrollo | Los hallazgos son descripciones sin consecuencia para el modelado, o una feature usa información que no existe en el momento de predecir. |
| 1, Insuficiente | Falta la exploración o el notebook de features, o corren sobre un archivo que no es el limpio del pipeline. |

## 2. Preparación sin fuga, del notebook al script

| Nivel | Descripción |
|---|---|
| 4, Excelente | La imputación, la codificación y el escalado están dentro de un `Pipeline` (o `ColumnTransformer`) que se ajusta solo con el conjunto de entrenamiento. Ninguna columna posterior al momento de predecir entra al modelo. La división corresponde al problema (por fecha si predice el futuro, al azar si no) y está justificada. `pipeline_proyecto.py` corre con `python pipeline_proyecto.py` desde una terminal nueva, contiene solo las líneas que construyen las features, y los notebooks de modelos lo importan. |
| 3, Logrado | La preparación no tiene fuga y el script corre, pero la división no está justificada o el script arrastra código de exploración. |
| 2, En desarrollo | Hay una fuga (una estadística calculada con todo el dataset antes de dividir, o una columna posterior al momento de predecir), o los notebooks copian la preparación en vez de importarla. |
| 1, Insuficiente | No hay preparación reproducible: los pasos se hacen a mano en el notebook. |

## 3. Comparación justa y sobreajuste

| Nivel | Descripción |
|---|---|
| 4, Excelente | La línea base corresponde al problema y su elección está justificada. Todos los candidatos (línea base, lineal, ensamblaje, red neuronal) usan la misma preparación y la misma división, y se comparan con la misma métrica. `resultados_proyecto.csv` tiene, por modelo, la métrica en entrenamiento y en prueba, la brecha y los segundos; el sobreajuste se diagnostica con esos números y la regularización muestra su efecto. La comparación incluye la prueba del LLM sobre las mismas filas, o explica por qué el problema no se puede plantear así. |
| 3, Logrado | La comparación es justa, pero falta una de estas piezas: la justificación de la línea base, el diagnóstico de sobreajuste con números, o la prueba del LLM. |
| 2, En desarrollo | Algún candidato usa otra preparación u otra división, falta la línea base, o falta la métrica de entrenamiento. |
| 1, Insuficiente | Hay un solo modelo, o los modelos no son comparables entre sí. |

## 4. Trazabilidad en MLflow

| Nivel | Descripción |
|---|---|
| 4, Excelente | Cada modelo tiene una corrida en un experimento con el nombre del proyecto, con sus hiperparámetros, cómo se dividieron los datos (semilla o fecha de corte), la huella del archivo de datos, la métrica en entrenamiento y en prueba, los segundos de entrenamiento y el pipeline entrenado como artefacto. La corrida final está marcada (`candidato` = `final`), su modelo se recupera del registro y reproduce exactamente la métrica registrada. `corridas_proyecto.csv` sale de una corrida completa, sin corridas repetidas ni de prueba. |
| 3, Logrado | Las corridas tienen todo, salvo un dato (la huella o la división), o la tabla exportada tiene corridas repetidas. |
| 2, En desarrollo | Las corridas registran métricas pero no cómo se obtuvieron (sin división ni huella), o el modelo final no se recupera del registro. |
| 1, Insuficiente | No hay registro en MLflow, o falta `corridas_proyecto.csv`. |

## 5. Validación, métrica del negocio y decisión

| Nivel | Descripción |
|---|---|
| 4, Excelente | El modelo final y el segundo mejor se evalúan con validación cruzada con el esquema que corresponde a los datos (temporal, por grupo o estratificado), justificado, y con un esquema al azar para comparar; la tabla tiene el promedio, la desviación y cada pliegue. La métrica del negocio refleja el costo del error más caro, con una estimación de cuánto cuesta. `docs/decision_modelo.md` se entiende sin haber estado en clase, cubre los seis puntos del enunciado con los números del registro y de la validación, y discute si la diferencia con el segundo mejor supera la variación entre pliegues. `proyecto/README.md` dice cómo se entrena y cuál es el modelo final. |
| 3, Logrado | Validación, métrica y decisión están, pero el esquema no está justificado, el costo del error no tiene estimación, o la decisión no discute la variación entre pliegues. |
| 2, En desarrollo | Hay un solo esquema o no corresponde a los datos, no hay métrica del negocio, o la decisión elige la mejor métrica de prueba sin más evidencia. |
| 1, Insuficiente | No hay validación cruzada o falta el documento de decisión. |

---
*Última actualización: 2026-11-04*
