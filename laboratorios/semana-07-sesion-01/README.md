# Semana 7, Sesión 1: Laboratorio Integrador I, pipeline de datos de un proyecto de principio a fin

> Objetivo de la sesión: integrar contenedores, infraestructura como código, orquestación, warehouse y procesamiento batch/streaming en el pipeline de datos de tu proyecto propio, sin exposición nueva de conceptos.

**Sin lectura nueva esta sesión.** Aprovecha para revisar las lecturas y referencias de las Semanas 3 a 6, y para tener a mano los archivos que ya construiste en cada una.

Este laboratorio no tiene tres ejercicios con dificultad creciente, como los de las Semanas 3 a 6. Es una sola tarea: dejar corriendo, de principio a fin, el pipeline completo de tu propio proyecto, usando exactamente lo que ya construiste. La checklist de abajo es la guía y también la rúbrica de la sesión: cada etapa que confirmas correr y entregar el archivo correcto a la siguiente es una etapa lista.

## Antes de empezar: reúne lo que ya tienes

Antes de correr nada, confirma que los cinco archivos o carpetas que tu propio proyecto ya generó en semanas anteriores están en [`psets/proyecto/`](../../psets/README.md), cada uno en su carpeta:

1. El Dockerfile de tu proyecto (Semana 3, Sesión 1), en la raíz de `psets/proyecto/`.
2. El `docker-compose.yml` o `main.tf` de tu infraestructura (Semana 3, Sesión 2), en `infra/`.
3. El flow de Kestra de tu pipeline de ingesta (Semana 4, Sesión 1), en `orquestacion/`.
4. Tu notebook de diagnóstico de calidad (Semana 4, Sesión 2), en `calidad/`. Hoy, las decisiones de limpieza que documentaste ahí pasan a un script (`calidad/limpiar.py`), que deja el archivo limpio en `data/processed/`: esta etapa corre sola dentro del pipeline, y un pipeline no abre notebooks ni sabe en qué orden corriste sus celdas. El script lleva solo las líneas que limpian, sin las celdas que usaste para mirar los datos.
5. El script que carga tu archivo limpio a tu warehouse de DuckDB (Semana 5, Sesión 1) y tu proyecto de dbt (Semana 5, Sesión 2), en `warehouse/`, y tu job de Spark sobre el histórico (Semana 6, Sesión 1), en `procesamiento/`.

Si alguno quedó dentro de la carpeta de un laboratorio, muévelo con `git mv` a su carpeta de `psets/proyecto/`. Las etapas 1 y 2 (contenedor e infraestructura) vienen del PSet 1; de la 3 a la 8, lo que verificas hoy es lo que entregas en el PSet 2.

Si te falta alguno, ese es tu primer bloqueo: resuélvelo antes de seguir, no lo saltes. El pipeline completo depende de que cada pieza exista.

Si trabajas en el Codespace, ábrelo para esta sesión con una máquina de 4 núcleos ("Change machine type"): Kestra, tu base de datos y, si tu proyecto lo usa, Redpanda corren al mismo tiempo. Kestra queda en el puerto 8080 y pgAdmin en el 8085, así que pueden estar levantados juntos.

## La cadena y el criterio de "funciona de principio a fin"

Cada etapa debe entregar exactamente lo que la siguiente espera recibir, no una versión aproximada. Ese es el criterio que estás verificando en cada casilla: no "¿corre el comando sin error?", sino "¿el archivo o la tabla que produce esta etapa es el mismo que la siguiente etapa lee de verdad?".

| Etapa | Semana | Verifica que... |
|---|---|---|
| 1. Contenedor | 3, Sesión 1 | `docker build` construye tu imagen sin error, y `docker run` (con tu volumen) produce el mismo resultado que correr tu script directo con Python |
| 2. Infraestructura | 3, Sesión 2 | `docker compose up` (o `terraform apply`) levanta tu base y el contenedor de ingesta se conecta a ella sin cambiar ninguna credencial a mano |
| 3. Orquestación | 4, Sesión 1 | tu flow de Kestra ejecuta la ingesta contenedorizada de la Etapa 1 (mismo tag de imagen, no uno viejo) con el reintento y el horario que configuraste |
| 4. Calidad | 4, Sesión 2 | tu script de limpieza, escrito a partir de tu notebook de diagnóstico, corre con `python3` sobre el archivo real que tu pipeline orquestado acumuló, no sobre el dataset de ejemplo de esa sesión |
| 5. Warehouse | 5, Sesión 1 | tu warehouse de DuckDB carga el archivo YA LIMPIO de la Etapa 4, no el crudo de la Etapa 1 |
| 6. Modelado | 5, Sesión 2 | `dbt run` y `dbt test` conectan al mismo archivo `.duckdb` de la Etapa 5 (revisa la ruta en tu `profiles.yml`) |
| 7. Batch | 6, Sesión 1 | tu job de Spark lee el mismo histórico limpio, y su resultado coincide con el que ya conocías de dbt o de pandas |
| 8. Streaming (opcional) | 6, Sesión 2 | si tu proyecto lo justifica, tu productor y consumidor corren contra el broker real; si no lo justifica, documenta por qué no |

## Checklist de verificación, etapa por etapa

Marca cada casilla solo después de correr el comando real, no antes.

**Etapa 1, contenedor:**
- [ ] `docker build -t <tu-imagen> .` termina sin error
- [ ] `docker run` (con tu volumen si tu proyecto lee o escribe datos) produce el mismo resultado que correr el script sin Docker

_Respuesta: ¿coincidió el resultado del contenedor con el resultado sin Docker? Si no, ¿qué diferencia encontraste?_

_(tu respuesta)_

**Etapa 2, infraestructura:**
- [ ] `docker compose up -d` (o `terraform apply`) levanta tu base de datos sin error
- [ ] el contenedor de ingesta de tu proyecto se conecta usando el nombre del servicio, no `localhost`

_Respuesta: ¿qué le pasó a tu ingesta en el primer intento de conexión, antes del reintento?_

_(tu respuesta)_

**Etapa 3, orquestación:**
- [ ] tu flow de Kestra ejecuta sin error, con el tag de imagen actual de la Etapa 1
- [ ] si forzaste una falla, el reintento configurado la resolvió

_Respuesta: si reconstruiste tu imagen de Docker después de crear el flow, ¿tuviste que actualizar algo en el flow para que usara la versión nueva?_

_(tu respuesta)_

**Etapa 4, calidad:**
- [ ] cada decisión de limpieza de tu notebook de diagnóstico está en tu script de limpieza, y el script corre de principio a fin con `python3`, sin abrir el notebook
- [ ] tu script de limpieza corre sobre el archivo real acumulado por tu pipeline orquestado, no sobre el dataset de ejemplo de esa sesión
- [ ] el archivo limpio que produce es el que vas a cargar en la Etapa 5, con el mismo nombre y ruta que usa el script de esa etapa

_Respuesta: ¿cuántos duplicados o valores mal tipados encontraste esta vez, corriendo contra tu histórico ya acumulado?_

_(tu respuesta)_

**Etapa 5, warehouse:**
- [ ] tu script de carga apunta al archivo LIMPIO (Etapa 4), no al crudo
- [ ] la cuenta de filas en el warehouse coincide con la cuenta de filas de tu archivo limpio

_Respuesta: ¿coincidieron las dos cuentas? Si no, ¿en qué paso se perdieron o se duplicaron filas?_

_(tu respuesta)_

**Etapa 6, modelado con dbt:**
- [ ] `dbt debug --profiles-dir .` confirma la conexión al mismo archivo `.duckdb` de la Etapa 5
- [ ] `dbt run --profiles-dir .` y `dbt test --profiles-dir .` terminan sin error

_Respuesta: ¿qué ruta tenía tu `profiles.yml`, y era relativa a la carpeta desde donde corriste el comando?_

_(tu respuesta)_

**Etapa 7, batch con Spark:**
- [ ] tu job de Spark lee el mismo archivo limpio de la Etapa 4
- [ ] el resultado agregado coincide con el que ya conocías de dbt o de pandas sobre el mismo dato

_Respuesta: ¿coincidió el número? Si no coincidió, ¿la diferencia viene de un archivo de entrada distinto, o de una transformación distinta?_

_(tu respuesta)_

**Etapa 8, streaming (opcional):**
- [ ] si tu proyecto justifica reaccionar en tiempo real, tu productor y consumidor corren contra el broker de Redpanda de la Semana 6, Sesión 2
- [ ] si tu proyecto no lo justifica, escribiste por qué no (repite el criterio de la Semana 6, Sesión 2: ¿la decisión pierde valor con datos de horas de antigüedad?)

_Respuesta:_

_(tu respuesta)_

## Antes de la próxima sesión

La próxima sesión es repaso de medio semestre, dirigido por las preguntas que traigan ustedes. Antes de esa sesión: lee ["What Is a Data Contract?"](https://www.ibm.com/think/topics/data-contract) (IBM), y trae al menos una pregunta sin resolver de las Semanas 1 a 7, la que más te haya costado.
