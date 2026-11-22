# PSet 4: Despliegue, monitoreo y comunicación del modelo

**Asignado:** Semana 12, Sesión 1. **Vence:** Semana 15, Sesión 2.

El modelo final de tu proyecto (PSet 3), puesto a trabajar: servido con el patrón que exige tu caso de uso, registrado con su versión, vigilado en producción y explicado a quien decide si se usa. Cada pieza sale del Ejercicio 3 de una sesión de las Semanas 12 a 15, y el Laboratorio Integrador II (Semana 15, Sesión 2) es la sesión para cerrar lo que falte. En la Semana 16, Sesión 1 presentas el proyecto completo tal como queda en este PSet.

## Entregables

Todo en [`../proyecto/`](../proyecto/):

| Pieza | Dónde | Sale de |
|---|---|---|
| El patrón de despliegue (batch u online), justificado por la latencia que exige tu caso de uso | `docs/despliegue.md` | Semana 12, Sesión 1 |
| Las pruebas de tu pipeline, corriendo en GitHub Actions en cada push | `modelado/test_pipeline_proyecto.py` | Semana 12, Sesión 1 |
| El modelo como servicio de predicción, con una API, sus pruebas y su propio contenedor | `servicio/` (`api.py`, `test_api.py`, `Dockerfile`, `requirements.txt` y el script que exporta el modelo desde MLflow) | Semana 12, Sesión 2 |
| El modelo registrado y versionado, y el servicio cargándolo desde el registro | `servicio/` y `docs/despliegue.md` | Semana 13, Sesión 1 |
| Las métricas del servicio: de sistema (latencia, disponibilidad) y de modelo (desempeño) | `servicio/` y `docs/despliegue.md` | Semana 13, Sesión 2 |
| La simulación de deriva sobre tus datos, el umbral de alerta elegido y la alerta en el servicio | `monitoreo/` y `servicio/` | Semana 14, Sesión 1 |
| La diapositiva de resultados en dos versiones, técnica y ejecutiva | `docs/resultados_tecnico.pdf` y `docs/resultados_ejecutivo.pdf` | Semana 14, Sesión 2 |
| El criterio de retirada: bajo qué condición se ajusta o se apaga el modelo | `docs/criterio_retirada.md` | Semana 15, Sesión 1 |

Cada laboratorio de las Semanas 12 a 15 detalla lo que pide su Ejercicio 3; esta tabla dice dónde queda cada pieza dentro del proyecto.

En `proyecto/README.md`, agrega la sección **Cómo correr el servicio**: cómo se construye y se levanta su contenedor, qué versión del modelo carga, y un ejemplo de petición con su respuesta.

## Lo que reviso

Que el último commit de la entrega tenga el check verde de GitHub Actions (las pruebas de `psets/proyecto` pasan en una máquina limpia), que el servicio corra desde un Codespace nuevo siguiendo tu `README.md`, y que lo que sirve sea el modelo que elegiste en el PSet 3: la versión registrada tiene que corresponder al `run_id` de `docs/decision_modelo.md`. Que cada decisión de este PSet (el patrón, las métricas, el umbral de la alerta, el criterio de retirada) esté justificada con lo que sabes de tu proyecto: la latencia que tolera la acción que habilita, el costo del error que definiste en el PSet 3, los datos que de verdad pueden cambiar.

## Cómo se evalúa

La rúbrica, con sus cinco criterios y niveles, está en [`rubrica.md`](./rubrica.md). Para entregar, sigue la sección "Cómo entregar" de [`psets/README.md`](../README.md): el tag de este PSet es `pset-04`.
