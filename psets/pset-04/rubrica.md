# PSet 4: Rúbrica de evaluación

> PSet 4 es uno de los 4 PSets del curso, que en conjunto valen 25% de la nota final. Los 4 PSets pesan igual entre sí (6.25% cada uno de la nota total), salvo que yo decida una ponderación distinta.

Cada criterio se califica en una escala de 0 a 4; la nota final del PSet es el promedio de los cinco.

## 1. Patrón de despliegue

| Nivel | Descripción |
|---|---|
| 4, Excelente | `docs/despliegue.md` elige batch u online a partir de la latencia que tolera la acción que habilita el proyecto, con un número (cada cuánto se necesita la predicción, en cuánto tiempo), y dice qué se pierde con el patrón descartado. |
| 3, Logrado | El patrón está justificado por la latencia, pero sin un número o sin discutir el patrón descartado. |
| 2, En desarrollo | El patrón se elige por preferencia técnica ("online porque es más moderno"), sin relación con el caso de uso. |
| 1, Insuficiente | No hay decisión de patrón. |

## 2. Servicio de predicción y sus pruebas

| Nivel | Descripción |
|---|---|
| 4, Excelente | El servicio se construye y se levanta con su contenedor siguiendo `proyecto/README.md`, responde a una petición con el ejemplo documentado, valida la entrada (una petición sin un dato obligatorio recibe 422, no una excepción del modelo) y calcula las features con las mismas funciones de `modelado/pipeline_proyecto.py`, importadas, no copiadas. Las versiones de sus librerías están fijadas. Las pruebas del pipeline y del servicio (al menos tres por archivo, con datos escritos a mano y un modelo de prueba) pasan en GitHub Actions en el commit de la entrega. |
| 3, Logrado | El servicio corre y responde, pero no valida la entrada, le falta un paso al README, o sus pruebas pasan en el Codespace y no en GitHub Actions (por ejemplo, porque leen un archivo que no está en el repositorio). |
| 2, En desarrollo | El servicio corre solo fuera del contenedor, reimplementa la preparación en vez de importarla, o no tiene pruebas. |
| 1, Insuficiente | No hay servicio, o no responde. |

## 3. Registro y versionado del modelo

| Nivel | Descripción |
|---|---|
| 4, Excelente | El modelo final está registrado con su versión, y la versión corresponde al `run_id` del PSet 3. El servicio carga el modelo desde el registro por su nombre y su versión (o alias), no desde un archivo copiado a mano. `docs/despliegue.md` explica cómo se pasa a una versión nueva y cómo se vuelve a la anterior. |
| 3, Logrado | El modelo está registrado y el servicio lo carga desde el registro, pero no está documentado cómo cambiar o revertir la versión. |
| 2, En desarrollo | El modelo está registrado, pero el servicio carga un archivo suelto, o la versión servida no corresponde a la elegida. |
| 1, Insuficiente | No hay registro del modelo. |

## 4. Monitoreo: métricas y deriva

| Nivel | Descripción |
|---|---|
| 4, Excelente | El servicio mide al menos una métrica de sistema (latencia, disponibilidad) y una de modelo (desempeño, o su mejor aproximación cuando el valor real llega tarde), y `docs/despliegue.md` dice por qué esas. El notebook de `monitoreo/` simula deriva sobre los datos del proyecto, distingue deriva de datos de deriva conceptual, y elige el umbral de la alerta con lo que muestra la simulación; la alerta está en el servicio. |
| 3, Logrado | Métricas y simulación están, pero el umbral no sale de la simulación o la alerta no está en el servicio. |
| 2, En desarrollo | Solo hay métricas de sistema, o la simulación no distingue los dos tipos de deriva. |
| 1, Insuficiente | No hay monitoreo. |

## 5. Comunicación y criterio de retirada

| Nivel | Descripción |
|---|---|
| 4, Excelente | Las dos versiones de la diapositiva de resultados cuentan el mismo resultado: la técnica con la métrica, la validación y las limitaciones; la ejecutiva con el efecto en la decisión de negocio y su costo, sin jerga. `docs/criterio_retirada.md` dice bajo qué condición medible se ajusta o se apaga el modelo, conectada con una métrica que el monitoreo ya registra, y qué riesgo operativo o ético la justifica. |
| 3, Logrado | Las dos versiones y el criterio están, pero alguna versión mezcla audiencias o el criterio no se puede medir con el monitoreo actual. |
| 2, En desarrollo | Una sola versión de la diapositiva, o un criterio de retirada genérico ("si el modelo empeora"). |
| 1, Insuficiente | Falta la comunicación o el criterio de retirada. |

---
*Última actualización: 2026-11-04*
