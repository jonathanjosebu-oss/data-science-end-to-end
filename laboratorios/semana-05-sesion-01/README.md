# Semana 5, Sesión 1: Data warehouse y data lake

> Objetivo de la sesión: elegir entre un data warehouse y un data lake para los datos de tu proyecto, justificando la decisión según el tipo de dato y el patrón de consulta.

**Lectura previa de esta sesión:** ["Data Lakes vs Data Warehouses Explained"](https://www.databricks.com/blog/data-lakes-vs-data-warehouses-what-your-organization-needs-know), Databricks.

**Referencia de esta sesión:** [BigQuery, documentación oficial](https://cloud.google.com/bigquery/docs/introduction). Este laboratorio usa DuckDB como warehouse local: cumple el mismo rol conceptual que BigQuery (base de datos analítica que recibe datos estructurados y sirve consultas SQL agregadas) sin necesitar ninguna cuenta de nube ni facturación, el mismo criterio que ya usó este curso con Docker/Terraform locales (Semana 3) y con Kestra local (Semana 4).

## Requisitos antes de esta sesión

1. **Python con `pandas` ya instalado**, el mismo de sesiones pasadas.
2. **DuckDB:** ya viene en el Codespace. En tu laptop, instálalo con `pip install -r requirements.txt` desde la raíz del repositorio, que fija la misma versión del Codespace. Verifica con:
   ```
   python -c "import duckdb; print(duckdb.__version__)"
   ```
3. Ten a mano el archivo (o los archivos) que tu pipeline orquestado de la Semana 4, Sesión 1 genera para tu proyecto. Si todavía no lo has corrido desde entonces, corre tu flow de Kestra al menos una vez antes de esta sesión.

## Antes de empezar

A partir de la lectura previa:

**Según el artículo, ¿qué tipo de dato y qué patrón de consulta hacen que un equipo prefiera un data warehouse en vez de un data lake?**

_(tu respuesta)_

**¿Y qué tipo de dato y qué patrón de consulta hacen que un equipo prefiera un data lake?**

_(tu respuesta)_

## Pregunta de apertura

Un equipo de finanzas necesita generar el mismo reporte de ventas todos los lunes, con columnas fijas (fecha, producto, monto), para cargarlo directo a un dashboard. Un equipo de machine learning recolecta clics, logs de la aplicación e imágenes de producto, en formatos distintos, sin saber todavía qué de todo eso va a usar en un modelo futuro. ¿Cuál de los dos necesita un data warehouse, y cuál un data lake?

_(tu respuesta)_

## Ejercicio 1: un warehouse local con pedidos y clientes

Archivo: [`starter/ejercicio1_warehouse.py`](./starter/ejercicio1_warehouse.py), sobre [`starter/pedidos.csv`](./starter/pedidos.csv) (pedidos de una tienda: categoría, cantidad, precio unitario) y [`starter/clientes.csv`](./starter/clientes.csv) (ciudad y segmento de cada cliente). El script ya se conecta al warehouse, imprime cada paso y cierra la conexión; faltan 4 `TODO`. Córrelo una vez antes de tocar nada:

```
cd laboratorios/semana-05-sesion-01/starter
python3 ejercicio1_warehouse.py
```

**Respuesta 1 (TODO 1), antes de ver la solución:** sin el TODO 1, `SHOW TABLES` sale vacío y aun así el Paso 3 devuelve filas. ¿De dónde las está leyendo? ¿Qué cambia cuando `pedidos` es una tabla del warehouse?

_(tu respuesta)_

**Respuesta 2 (TODO 1):** con la tabla ya creada, si alguien edita `pedidos.csv`, ¿la tabla `pedidos` se actualiza sola, o hay que volver a cargarla?

_(tu respuesta)_

**Respuesta 3 (TODO 3):** sin el TODO 3, el Paso 3 devuelve 10 filas, una por pedido. ¿Cuántas esperas después de agregar por categoría?

_(tu respuesta)_

**Respuesta 4 (TODO 4):** ni `pedidos` ni `clientes` responden por separado "¿cuánto se vendió por ciudad?". ¿Qué instrucción de SQL las combina, y por qué columna?

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

## Ejercicio 2: ventas por categoría

Solo o en pareja. Archivo: [`starter/ejercicio2_ventas.py`](./starter/ejercicio2_ventas.py), sobre [`starter/ventas.csv`](./starter/ventas.csv) y [`starter/productos.csv`](./starter/productos.csv). Son los mismos pasos del Ejercicio 1, más uno nuevo (TODO 5). Al final, el script imprime una comprobación por TODO: completa los 5 hasta que todas digan `OK`.

```
python3 ejercicio2_ventas.py
```

**Respuesta 1:** en el Paso 3 aparece un `id_producto` que no está en `productos.csv`. ¿Cuál, y qué le pasa a esa venta en el `JOIN` del Paso 4?

_(tu respuesta)_

**Respuesta 2:** el monto total del Paso 4 no incluye esa venta, y la consulta no dio ningún error. ¿Cómo te darías cuenta de esto en un warehouse con millones de filas?

_(tu respuesta)_

**Si terminas antes:** ¿qué tipo de `JOIN` conservaría esa venta en el resultado, y qué valor tendría su `categoria`?

_(tu respuesta)_

## Ejercicio 3: el warehouse de tu propio proyecto

Carga el archivo real que tu pipeline orquestado (Semana 4, Sesión 1) genera para tu proyecto a un warehouse de DuckDB propio, y escribe tus primeras consultas. Parte de la plantilla [`plantilla-warehouse/construir_warehouse.py`](./plantilla-warehouse/construir_warehouse.py), que trae los `TODO` marcados en vez del script en blanco: cópiala a `psets/proyecto/warehouse/` y complétala ahí.

### Paso 1: conecta y carga tu archivo (5 minutos)

Reemplaza el nombre del archivo `.duckdb`, la ruta de tu CSV (o el formato que tu proyecto genere) y el nombre de la tabla.

_(tu nombre de archivo `.duckdb` y de tabla elegidos)_

### Paso 2: primera consulta, cuántas filas cargaste (5 minutos)

Confirma que el número de filas coincide con lo que esperabas de tu archivo de origen.

_(cuántas filas cargaste, y si coincide con lo esperado)_

### Paso 3: una agregación que responda una pregunta real de tu proyecto (10 minutos)

Elige una columna categórica de tu dataset y agrégala con `GROUP BY`, pensando en una pregunta que de verdad te interese para tu proyecto, no una agregación arbitraria.

_(tu consulta, qué pregunta responde, y qué encontraste)_

## Antes de la próxima sesión

Ya tienes tus datos en un warehouse y corriste tus primeras consultas.

Pregunta: si mañana necesitas ese mismo tipo de consulta pero con una columna calculada nueva, y la próxima semana alguien más del equipo necesita otra variación de la misma lógica, ¿qué pasa si cada quien la escribe como un SQL nuevo desde cero?

_(tu respuesta)_
