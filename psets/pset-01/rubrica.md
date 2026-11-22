# PSet 1: Rúbrica de evaluación

> PSet 1 es uno de los 4 PSets del curso, que en conjunto valen 25% de la nota final. Los 4 PSets pesan igual entre sí (6.25% cada uno de la nota total), salvo que yo decida una ponderación distinta.

Los cuatro entregables de PSet 1 (Canvas de Viabilidad y Riesgos, Documento de propuesta, Presentación de negocio y el ambiente del proyecto) se evalúan como una sola entrega, con los seis criterios de esta rúbrica. Cada criterio se califica en una escala de 0 a 4; la nota final del PSet es el promedio de los seis.

## 1. Formulación del problema y métrica de éxito

| Nivel | Descripción |
|---|---|
| 4, Excelente | La predicción es una salida concreta y medible (no el objetivo de negocio completo); la métrica de éxito es verificable con datos reales identificados, con punto de comparación (grupo de control o línea base); el umbral de decisión está justificado con una razón de negocio explícita, nombrando qué tipo de error cuesta más caro. |
| 3, Logrado | Predicción y métrica cumplen lo anterior, pero el umbral de decisión no tiene una justificación de negocio explícita, o falta el punto de comparación. |
| 2, En desarrollo | La predicción todavía confunde el objetivo de negocio con la salida concreta a predecir (ej. "predecir si el proyecto va a tener éxito"), o la métrica de éxito no es verificable con datos reales identificados. |
| 1, Insuficiente | No hay una predicción concreta ni una métrica de éxito, o ambas son genéricas ("mejorar la retención", "usar IA para optimizar"). |

## 2. Viabilidad técnica (predicción y datos)

| Nivel | Descripción |
|---|---|
| 4, Excelente | Cada dato necesario tiene su estado real marcado (ya existe con acceso confirmado / existe sin acceso confirmado / no existe todavía), con la fuente identificada cuando aplica. |
| 3, Logrado | Los datos necesarios están identificados, pero al menos uno no tiene su estado de acceso verificado o documentado. |
| 2, En desarrollo | Se listan los datos en términos generales ("datos de uso", "información de ventas") sin especificar de dónde saldrían ni si existen. |
| 1, Insuficiente | No se abordan los datos necesarios, o se asume sin evidencia que "los datos existen". |

## 3. Viabilidad de negocio (acción, juicio, resultado)

| Nivel | Descripción |
|---|---|
| 4, Excelente | La acción que cambia está claramente definida y depende directamente de la predicción; el juicio humano (quién decide, en qué casos el sistema actúa solo) está explícito; el resultado se mide con una métrica de negocio, no solo una métrica técnica del modelo. |
| 3, Logrado | Los tres elementos están presentes, pero alguno queda parcialmente desarrollado (ej. el juicio humano se menciona pero no se explica en qué casos interviene). |
| 2, En desarrollo | La predicción no está atada a una acción concreta ("sería interesante saber esto"), sin que quede claro qué decisión cambiaría. |
| 1, Insuficiente | No se aborda la viabilidad de negocio, o se limita a afirmar que el proyecto "generaría valor" sin especificar cómo. |

## 4. Riesgos

| Nivel | Descripción |
|---|---|
| 4, Excelente | Al menos dos riesgos, cada uno nombrando el supuesto concreto que rompe (no una descripción genérica), con evidencia real o un plan concreto de verificación, y una estimación de gravedad si ocurre. |
| 3, Logrado | Al menos dos riesgos con el supuesto identificado, pero sin evidencia ni plan de verificación para al menos uno. |
| 2, En desarrollo | Los riesgos son genéricos ("podría fallar el modelo", "podría no gustarle a los usuarios"), sin nombrar el supuesto que rompen. |
| 1, Insuficiente | Menos de dos riesgos, o ninguno verificable. |

## 5. Calidad del paquete como material profesional

| Nivel | Descripción |
|---|---|
| 4, Excelente | El documento de propuesta se entiende sin haber estado en la sesión de clase, en el orden pedido (problema/métrica, viabilidad técnica, viabilidad de negocio, riesgos), entre 1 y 2 páginas. La presentación sigue el formato de pitch a un patrocinador (problema y oportunidad, solución, evidencia de viabilidad, riesgos, qué se necesita para avanzar), no el formato de diapositiva de clase, en 5 a 8 diapositivas. Los tres entregables son consistentes entre sí (mismos datos, misma predicción, mismos riesgos). |
| 3, Logrado | Los tres entregables están completos y son consistentes entre sí, pero alguno se sale del formato pedido (ej. la presentación repite el formato de texto plano de las diapositivas de clase, o el documento excede las 2 páginas sin necesidad). |
| 2, En desarrollo | Falta uno de los tres entregables, o hay inconsistencias notorias entre ellos (datos distintos, riesgos distintos). |
| 1, Insuficiente | Falta más de un entregable, o el contenido es copia directa del laboratorio de clase sin revisión ni mejora. |

## 6. Ambiente reproducible: contenedor e infraestructura

| Nivel | Descripción |
|---|---|
| 4, Excelente | `docker build` construye la imagen sin error, en el orden que aprovecha la cache (dependencias antes que código), y `docker run` con un volumen produce el mismo resultado que correr el script de ingesta sin Docker. `requirements.txt` fija las versiones. La base de datos se levanta con un solo comando (`docker compose up -d` o `terraform apply`), y la ingesta se conecta por nombre de servicio, no por `localhost`, con un reintento que tolera que la base todavía no acepte conexiones. La sección "Datos" de `proyecto/README.md` permite obtener los datos desde cero. |
| 3, Logrado | Imagen e infraestructura funcionan, pero falta uno de los detalles anteriores (versiones sin fijar, orden de instrucciones que invalida la cache, conexión sin reintento, sección "Datos" incompleta). |
| 2, En desarrollo | La imagen se construye, pero el contenedor no produce el mismo resultado que el script, o la infraestructura necesita pasos a mano que no están documentados. |
| 1, Insuficiente | Falta el Dockerfile o la infraestructura, o ninguno de los dos corre. |

## Nota sobre el criterio central

El criterio que atraviesa los cinco primeros puntos, tomado directamente del enunciado de PSet 1: la viabilidad técnica y de negocio debe estar sustentada con evidencia concreta del proyecto propio, no con afirmaciones genéricas, y los riesgos identificados deben ser específicos y verificables, siguiendo el mismo criterio de evidencia usado en la Semana 1, Sesión 2 y en el laboratorio de Semana 2, Sesión 2. Un entregable que suena profesional en el formato pero es vago en el contenido no califica como Excelente en ningún criterio, aunque esté bien escrito.

---
*Última actualización: 2026-11-04*
