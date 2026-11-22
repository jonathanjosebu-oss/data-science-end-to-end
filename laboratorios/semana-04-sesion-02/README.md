# Semana 4, Sesión 2: Calidad de datos, diagnóstico y limpieza de los datos

> Objetivo de la sesión: diagnosticar problemas de calidad en el dataset de tu proyecto (duplicados, valores faltantes, inconsistencias de esquema) y justificar qué estrategia de limpieza aplica a cada uno.

**Lectura previa de esta sesión:** ["An Introduction to Data Quality"](https://medium.com/towards-data-science/an-introduction-to-data-quality-951cc6fe0274), Towards Data Science / Medium.

**Referencia de esta sesión:** *Designing Machine Learning Systems*, Cap. 3, Data Engineering Fundamentals (Chip Huyen).

## Requisitos antes de esta sesión

Confirma que tienes pandas (ya viene en el Codespace; en tu laptop, `pip install -r requirements.txt` desde la raíz del repositorio) y acceso al dataset real de tu proyecto, aunque sea en una versión parcial o de muestra.

Los laboratorios de hoy son notebooks de Jupyter (`.ipynb`), los primeros del curso: un diagnóstico es algo que lees para decidir, no algo que corre solo en el pipeline. En el Codespace, ábrelos desde el explorador de VS Code y, la primera vez, elige el kernel de Python 3.11 (sección "Notebooks y scripts" del README de la raíz del repositorio).

## Antes de empezar

A partir de la lectura previa:

**Según el artículo, ¿por qué un modelo puede entrenar sin ningún error y producir métricas razonables, aunque los datos de entrada tengan problemas serios de calidad?**

_(tu respuesta)_

**El artículo distingue varias dimensiones de calidad de datos. ¿Cuál te parece más difícil de detectar solo con un vistazo rápido al dataset, sin código?**

_(tu respuesta)_

## Pregunta de apertura

Tu modelo entrena sin ningún error, y las métricas se ven razonables. ¿Eso significa que los datos de entrada estaban bien?

_(tu respuesta)_

## Ejercicio 1: diagnóstico completo de un archivo de sensores

Notebook: [`starter/ejercicio1_diagnostico.ipynb`](./starter/ejercicio1_diagnostico.ipynb), sobre [`starter/lecturas_sensores.csv`](./starter/lecturas_sensores.csv). Ya lee el archivo, muestra cada paso y guarda el resultado; faltan las líneas que hacen el diagnóstico, marcadas como `TODO 1` a `TODO 4`. Córrelo completo una vez antes de tocar nada (**Run All**).

**Respuesta 1 (TODO 1), antes de ver la solución:** sin el TODO 1, el notebook dice que quedan 10 filas. Mirando el CSV, ¿cuántas esperas que queden después de quitar las filas repetidas, y con qué método de pandas las contarías antes de quitarlas?

_(tu respuesta)_

**Respuesta 2 (TODO 2 y 3):** `isna()` va a contar 1 temperatura faltante. ¿Cuántas esperas después de convertir `temperatura` a número con `errors="coerce"`, y de dónde sale la diferencia?

_(tu respuesta)_

**Respuesta 3 (TODO 4):** sin el TODO 4, el notebook convierte las fechas con `pd.to_datetime` sin indicar formato. ¿Qué fecha le asignó a S3 (`01/02/2026`) y a S8 (`03/02/2026`)? ¿Apareció algún error?

_(tu respuesta)_

**Lo que confirmó la salida, TODO por TODO:**

_(anota los números que no esperabas)_

## Durante el ConcepTest

**Tu voto, antes de discutir en pareja** (A, B, C o D):

_(tu voto)_

**Tu razonamiento:**

_(tu respuesta)_

**Después de discutir en pareja, ¿cambiaste de voto? ¿Por qué?**

_(tu respuesta)_

## Ejercicio 2: pedidos de una tienda

Solo o en pareja. Notebook: [`starter/ejercicio2_pedidos.ipynb`](./starter/ejercicio2_pedidos.ipynb), sobre [`starter/pedidos_tienda.csv`](./starter/pedidos_tienda.csv). Son los mismos pasos del Ejercicio 1 sobre otro archivo, más uno nuevo (TODO 5). La última celda imprime una comprobación por TODO: completa los 5 hasta que todas digan `OK`.

**Respuesta 1:** la columna `monto` usa dos marcadores distintos para un dato que no existe. ¿Cuáles son, y cuántos de ellos contó `isna()` antes de convertir?

_(tu respuesta)_

**Respuesta 2:** después de quitar los duplicados, el TODO 5 encuentra un `pedido_id` que todavía aparece dos veces. ¿Por qué `duplicated()` no lo marcó? ¿Qué necesitarías saber del negocio para decidir cuál de las dos filas conservar?

_(tu respuesta)_

**Si terminas antes:** `cantidad` también tiene faltantes, pero `dtypes` la muestra como `float64` aunque todas sus cantidades son enteras. ¿Por qué?

_(tu respuesta)_

## Ejercicio 3: diagnóstico del dataset de tu proyecto

Copia la plantilla [`plantilla-diagnostico/diagnostico_proyecto.ipynb`](./plantilla-diagnostico/diagnostico_proyecto.ipynb) a `psets/proyecto/calidad/`. Ahí corres sobre tu propio dataset las mismas verificaciones de los Ejercicios 1 y 2 (`duplicated()`, `isna()`, `dtypes`, conversión con `errors="coerce"`, revisión manual de formatos mezclados), y documentas lo que encuentres en las celdas de texto, debajo de la verificación que lo muestra.

El resultado de hoy es el diagnóstico documentado y justificado, no todavía la limpieza completa implementada: antes de corregir hay que entender qué se está corrigiendo y por qué, como muestra el ConcepTest de esta sesión. La limpieza que decidas aquí pasa a un script de tu pipeline en la Semana 7.

### Paso 1: corre las verificaciones (10 minutos)

Reemplaza la ruta del archivo y corre las celdas de código de cada sección. En la sección de esquema, agrega las conversiones que necesiten tus columnas, adaptando el código de los Ejercicios 1 y 2.

### Paso 2: revisa manualmente lo que el código no captura solo (5 minutos)

Duplicados, faltantes y tipos se detectan con código; los formatos mezclados (fechas, categorías escritas de más de una forma, unidades distintas) muchas veces requieren mirar los valores distintos de una columna (`datos["columna"].unique()`) para notarlos. La celda de valores faltantes ya los muestra para cada columna de texto.

### Paso 3: documenta el diagnóstico (5 minutos)

Responde las preguntas de cada sección del notebook. Para cada problema encontrado, documenta la estrategia que aplicarías y por qué, no solo que el problema existe. Antes de hacer commit, reinicia el kernel y corre todo.

**Ruta de tu notebook de diagnóstico en tu fork:**

_(tu respuesta)_

## Antes de la próxima sesión

Ya diagnosticaste los problemas de calidad de tu dataset.

Pregunta: ¿cómo decides, con evidencia y no solo con intuición, qué variables de ese dataset ayudan a predecir lo que tu proyecto necesita predecir, y cuáles solo parecen ayudar?

_(tu respuesta)_
