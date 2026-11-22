# Semana 5, Sesión 2: Modelado analítico (analytics engineering)

> Objetivo de la sesión: construir un modelo de datos en capas (staging, intermedia, marts) con pruebas y documentación para los datos de tu proyecto.

**Lectura previa de esta sesión:** ["What is analytics engineering?"](https://www.getdbt.com/blog/what-is-analytics-engineering), dbt Labs.

**Referencia de esta sesión:** [dbt, documentación oficial](https://docs.getdbt.com/docs/introduction). Este laboratorio usa `dbt-duckdb`, el adaptador que conecta dbt al mismo warehouse de DuckDB que construiste la sesión pasada: dbt corre igual de local que DuckDB, sin ningún servicio ni cuenta adicional.

## Requisitos antes de esta sesión

1. **El warehouse de DuckDB de la Sesión 1**, con los datos de tu proyecto ya cargados (el archivo `.duckdb` del Ejercicio 3 de la sesión pasada).
2. **dbt con el adaptador de DuckDB:** ya viene en el Codespace. En tu laptop, instálalo con `pip install -r requirements.txt` desde la raíz del repositorio. Verifica con:
   ```
   dbt --version
   ```
   Deberías ver `duckdb` listado en la sección de plugins.

## Antes de empezar

A partir de la lectura previa:

**Según el artículo, ¿qué hace un analytics engineer que no hace ni un ingeniero de datos puro ni un analista puro?**

_(tu respuesta)_

**El artículo describe el flujo de trabajo de dbt (escribir SQL, dbt lo convierte en tablas o vistas). ¿Qué gana ese SQL por vivir dentro de un proyecto de dbt en vez de pegarse directo en una consola de SQL?**

_(tu respuesta)_

## Pregunta de apertura

Imagina un solo archivo SQL de 200 líneas: limpia los datos crudos, calcula columnas de negocio, une varias tablas y agrega el resultado final, todo en una sola consulta con subconsultas anidadas. Funciona. ¿Por qué no dejarlo así?

_(tu respuesta)_

## Ejercicio 1: pedidos por ciudad, en tres capas

Carpeta: [`starter/ejercicio1/`](./starter/ejercicio1/), un proyecto de dbt completo sobre las mismas tablas de la Sesión 1. Ya corre de principio a fin, pero cada capa tiene un `TODO`: staging con `select *`, sin prueba sobre `stg_pedidos`, un modelo intermedio que lee las tablas crudas por su nombre, y un mart sin agregar. Córrelo una vez antes de tocar nada:

```
cd laboratorios/semana-05-sesion-02/starter/ejercicio1
python3 cargar_raw.py
dbt run --profiles-dir .
dbt test --profiles-dir .
```

**Respuesta 1 (TODO 1), antes de ver la solución:** si `stg_pedidos` solo selecciona columnas de `raw_pedidos`, sin ningún cálculo, ¿qué sentido tiene un modelo aparte en vez de consultar `raw_pedidos` directamente?

_(tu respuesta)_

**Respuesta 2 (TODO 2):** ¿sobre qué columna de `stg_pedidos` pondrías la prueba `unique`? ¿Qué tendría que pasar en `pedidos.csv` para que falle?

_(tu respuesta)_

**Respuesta 3 (TODO 3):** mira el orden en que `dbt run` construyó los modelos. ¿Por qué `int_pedidos_con_cliente` salió primero, antes que los modelos de staging de los que depende? ¿Qué cambia con `ref()`?

_(tu respuesta)_

**Respuesta 4 (TODO 4):** si mañana cambias cómo se calcula `monto_total` en el modelo intermedio, ¿tienes que tocar también el mart?

_(tu respuesta)_

**Lo que confirmó la salida, TODO por TODO:**

_(anota el orden de `dbt run` antes y después del TODO 3, y lo que no esperabas)_

## Durante el ConcepTest

**Tu voto, antes de discutir en pareja** (A, B, C o D):

_(tu voto)_

**Tu razonamiento:**

_(tu respuesta)_

**Después de discutir en pareja, ¿cambiaste de voto? ¿Por qué?**

_(tu respuesta)_

## Ejercicio 2: ventas por categoría, en tres capas

Solo o en pareja. Carpeta: [`starter/ejercicio2/`](./starter/ejercicio2/), las ventas y productos de la Sesión 1 (con una diferencia en `ventas.csv` que vas a encontrar con una prueba). Son las mismas cuatro capas del Ejercicio 1 (TODO 1 a 4), más uno nuevo (TODO 5). Después de cada cambio, corre:

```
python3 cargar_raw.py
dbt run --profiles-dir .
dbt test --profiles-dir .
python3 comprobar.py
```

`comprobar.py` imprime `OK` o `revisa` por cada TODO: complétalos hasta que todos digan `OK`.

**Respuesta 1:** ¿qué prueba falló primero, y qué fila de `ventas.csv` la hizo fallar?

_(tu respuesta)_

**Respuesta 2 (TODO 5):** corregiste la causa en `stg_ventas`, no en `ventas.csv`. ¿Por qué ahí y no en el archivo, si el archivo es el que está mal?

_(tu respuesta)_

**Si terminas antes:** sin el TODO 5, ¿cuánto daba el monto de papelería en el mart, y cuánto da después? ¿Qué habría pasado con ese número si nadie hubiera escrito la prueba?

_(tu respuesta)_

## Ejercicio 3: modela en capas los datos de tu propio proyecto

Usa el mismo patrón de los Ejercicios 1 y 2 (staging, intermedia, marts), aplicado a la tabla que cargaste a tu warehouse en la Sesión 1. Parte de la plantilla [`plantilla-dbt/`](./plantilla-dbt/), que trae los `TODO` marcados en cada archivo en vez del proyecto en blanco: copia la carpeta completa a `psets/proyecto/warehouse/dbt/` y trabaja ahí, al lado del `.duckdb` de la Sesión 1.

### Paso 1: staging (7 minutos)

Renombra `models/staging/stg_TODO.sql` a `stg_<tu_tabla>.sql`, selecciona las columnas de tu tabla cruda, y agrega al menos una prueba (`unique` o `not_null`) en `schema.yml` sobre la columna que identifica cada fila.

_(tu modelo de staging y la prueba que elegiste)_

### Paso 2: intermedia y marts (13 minutos)

Renombra y completa `models/intermedia/int_TODO.sql` con una transformación o combinación de tablas de staging (usando `{{ ref(...) }}`), y `models/marts/marts_TODO.sql` con la agregación final que responda una pregunta real de tu proyecto.

_(tus modelos y qué pregunta responde tu marts)_

Corre y prueba tu proyecto:

```
dbt run --profiles-dir .
dbt test --profiles-dir .
```

_(qué mostró `dbt run`, y si alguna prueba falló)_

## Antes de la próxima sesión

Ya tienes tus datos organizados en capas, con pruebas que fallan si algo se rompe.

Pregunta: todo lo que hiciste hasta ahora (warehouse, capas, pruebas) asume que tus datos caben enteros en la memoria de tu computadora. ¿Qué pasa el día en que el historial completo de tu proyecto ya no cabe?

_(tu respuesta)_
