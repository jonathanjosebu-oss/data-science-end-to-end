# PSet 2: Rúbrica de evaluación

> PSet 2 es uno de los 4 PSets del curso, que en conjunto valen 25% de la nota final. Los 4 PSets pesan igual entre sí (6.25% cada uno de la nota total), salvo que yo decida una ponderación distinta.

Cada criterio se califica en una escala de 0 a 4; la nota final del PSet es el promedio de los cuatro.

## 1. Orquestación

| Nivel | Descripción |
|---|---|
| 4, Excelente | El flow corre la imagen actual del proyecto (el mismo tag que construye el Dockerfile) sin error. El reintento (`maxAttempts`, `interval`) y el horario (expresión cron) están justificados por cómo falla y cada cuánto cambia la fuente de datos de tu proyecto, no copiados del laboratorio. |
| 3, Logrado | El flow corre con reintento y horario, pero alguno de los dos no tiene una justificación propia del proyecto. |
| 2, En desarrollo | El flow corre, pero sin reintento o sin horario, o con un tag de imagen que ya no corresponde al Dockerfile actual. |
| 1, Insuficiente | No hay flow, o no corre. |

## 2. Calidad de datos

| Nivel | Descripción |
|---|---|
| 4, Excelente | El notebook de diagnóstico documenta cada problema encontrado (duplicados, faltantes, tipos, formatos mezclados) con la verificación que lo muestra y la estrategia elegida, con su porqué. Cada decisión del diagnóstico está implementada en `limpiar.py`, que corre de principio a fin sin abrir el notebook, sobre el histórico real acumulado por el pipeline, y deja en `data/processed/` el archivo que lee la etapa siguiente. |
| 3, Logrado | Diagnóstico y limpieza completos, pero alguna decisión del diagnóstico no está en el script, o una estrategia no tiene justificación. |
| 2, En desarrollo | El diagnóstico lista problemas sin estrategia, o la limpieza sigue en el notebook y no en un script. |
| 1, Insuficiente | Falta el diagnóstico o la limpieza. |

## 3. Warehouse, modelado en capas y procesamiento batch

| Nivel | Descripción |
|---|---|
| 4, Excelente | La carga a DuckDB lee el archivo limpio, y su cuenta de filas coincide con la del archivo. El proyecto de dbt tiene las tres capas (staging, intermedia, marts), al menos una prueba sobre la columna que identifica cada fila, `dbt run` y `dbt test` terminan sin error contra el mismo `.duckdb`, y el mart responde una pregunta de tu proyecto. El job de Spark lee el mismo archivo limpio y su resultado coincide con el de dbt o pandas. |
| 3, Logrado | Las tres piezas funcionan, pero una no conecta con la anterior (el warehouse carga el archivo crudo, dbt apunta a otro `.duckdb`, Spark lee otro archivo) o una cuenta no se verificó. |
| 2, En desarrollo | Falta una de las tres piezas, o dbt no tiene pruebas, o sus pruebas fallan. |
| 1, Insuficiente | Faltan dos o más piezas. |

## 4. Cadena de principio a fin y documentación

| Nivel | Descripción |
|---|---|
| 4, Excelente | Siguiendo `proyecto/README.md` desde un Codespace nuevo, la cadena corre completa, desde la imagen y la infraestructura del PSet 1 hasta el warehouse, sin pasos que no estén escritos. La decisión de streaming o batch está justificada con el criterio de la Semana 6, Sesión 2, y si el proyecto usa streaming, el productor y el consumidor corren contra el broker. Ningún dato ni contraseña está en el repositorio. |
| 3, Logrado | La cadena corre completa, pero hace falta un paso que el README no dice, o la decisión de streaming no tiene justificación. |
| 2, En desarrollo | La cadena se corta en una etapa, o el README no permite saber en qué orden se corre. |
| 1, Insuficiente | No hay README del proyecto, o la cadena se corta en más de una etapa. |

---
*Última actualización: 2026-11-04*
