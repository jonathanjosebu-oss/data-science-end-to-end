# Semana 3, Sesión 1: Contenedores para pipelines de proyectos

> Objetivo de la sesión: empaquetar el entorno de trabajo de tu proyecto propio en una imagen de Docker reproducible, y explicar qué problema de "funciona en mi máquina" resuelve un contenedor.

**Lectura previa de esta sesión:** ["How Docker Can Help You Become a More Effective Data Scientist"](https://medium.com/data-science/how-docker-can-help-you-become-a-more-effective-data-scientist-7fc048ef91d5), Towards Data Science / Medium.

**Referencia de esta sesión:** [Data Engineering Zoomcamp, Módulo 1 (DataTalksClub)](https://github.com/DataTalksClub/data-engineering-zoomcamp/tree/main/01-docker-terraform).

## Requisitos antes de esta sesión

Abre el Codespace de tu fork (ver [Tu ambiente de desarrollo](../../README.md#tu-ambiente-de-desarrollo) en el README del repositorio): Docker ya viene instalado. Confirma que funciona corriendo `docker run hello-world` en la terminal. Si prefieres trabajar en tu laptop, instala [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, Mac o Linux) y corre la misma verificación. Si tu proyecto necesita GPU o un ambiente que no corre bien en ninguna de las dos opciones, avísame antes de esta sesión.

El Codespace también es un contenedor, pero no reemplaza el Dockerfile que construyes hoy. El Codespace trae las herramientas del curso, iguales para todos. La imagen de tu proyecto trae solo lo que tu proyecto necesita para correr en cualquier máquina, incluida una que nunca abrió este repositorio.

## Antes de empezar

A partir de la lectura previa:

**Según el artículo, ¿qué diferencia hay entre una imagen de Docker y un contenedor?**

_(tu respuesta)_

**¿Qué captura Docker, además de las librerías de Python, que un `requirements.txt` por sí solo no captura?**

_(tu respuesta)_

## Pregunta de apertura

¿Por qué un notebook que corre perfecto en mi laptop podría fallar por completo en la tuya, aunque ambos tengan el mismo código?

_(tu respuesta)_

## Ejercicio 1: la imagen de un script con pandas y datos

Carpeta: [`starter/ejercicio1/`](./starter/ejercicio1/). `procesar.py` lee `datos/ventas.csv` con pandas, imprime el total por producto y guarda `datos/resumen_ventas.csv`. El [`Dockerfile`](./starter/ejercicio1/Dockerfile) ya construye, pero tiene dos `TODO`. Constrúyelo y córrelo antes de tocar nada:

```
cd laboratorios/semana-03-sesion-01/starter/ejercicio1
docker build -t procesar-ventas .
docker run procesar-ventas
```

**Respuesta 1, antes de ver la solución:** el Dockerfile fija `python:3.11-slim` y no solo `python`. ¿Qué cambiaría en un año si dijera solo `python`?

_(tu respuesta)_

**Respuesta 2 (TODO 1):** si cambias una línea de `procesar.py` y vuelves a construir, ¿qué pasos se repiten? ¿Cómo reordenarías las líneas para que `pip install` no se repita?

_(tu respuesta)_

**Respuesta 3 (TODO 2):** `docker run procesar-ventas` termina sin imprimir nada y sin error. ¿Qué le falta a la imagen?

_(tu respuesta)_

**Respuesta 4 (TODO 3, el comando de `docker run`):** con los TODO 1 y 2 resueltos, la imagen solo copia `procesar.py`. ¿Encuentra `datos/ventas.csv` al correr? Y si lo encontrara, ¿dónde quedaría `resumen_ventas.csv` cuando el contenedor termina?

_(tu respuesta)_

**Lo que confirmó la salida, TODO por TODO:**

_(anota el Dockerfile final, el comando con `-v`, y lo que no esperabas)_

## Durante el ConcepTest

**Tu voto, antes de discutir en pareja** (A, B, C o D):

_(tu voto)_

**Tu razonamiento:**

_(tu respuesta)_

**Después de discutir en pareja, ¿cambiaste de voto? ¿Por qué?**

_(tu respuesta)_

## Ejercicio 2: la imagen de un resumen de clientes

Solo o en pareja. Carpeta: [`starter/ejercicio2/`](./starter/ejercicio2/). `resumir_clientes.py` cuenta los clientes por ciudad y guarda `datos/clientes_por_ciudad.csv`; `contar_filas.py` guarda el total de clientes en `datos/conteo.txt`. Escribe el `Dockerfile` con el mismo patrón del Ejercicio 1 (TODO 1 a 3), y después:

- **TODO 4:** corre la imagen con un volumen para que `clientes_por_ciudad.csv` aparezca en tu carpeta `datos/`.
- **TODO 5:** corre `contar_filas.py` con la misma imagen, sin cambiar el Dockerfile ni volver a construir. Pista: lo que escribes después del nombre de la imagen en `docker run` reemplaza el `CMD`.

Revisa tu avance con:

```
bash comprobar.sh
```

**Respuesta 1:** ¿qué comando usaste en el TODO 5? ¿Qué significa, entonces, que `CMD` sea el comando "por defecto"?

_(tu respuesta)_

**Respuesta 2:** si borras `datos/clientes_por_ciudad.csv` de tu carpeta y corres la imagen otra vez sin `-v`, ¿qué pasa?

_(tu respuesta)_

**Si terminas antes:** `contar_filas.py` no usa pandas. ¿Valdría la pena una imagen aparte para él, sin `pip install`? ¿Qué ganarías y qué perderías?

_(tu respuesta)_

## Ejercicio 3: el Dockerfile de tu propio proyecto

Usa el mismo patrón de los Ejercicios 1 y 2, aplicado al ambiente de tu proyecto. Parte de la plantilla [`plantilla-dockerfile/Dockerfile`](./plantilla-dockerfile/Dockerfile), que trae los `TODO` marcados en vez del Dockerfile en blanco. Tu proyecto vive en [`psets/proyecto/`](../../psets/README.md) durante todo el semestre: copia la plantilla a la raíz de `psets/proyecto/` y trabaja ahí, con tu script de ingesta en `psets/proyecto/ingesta/`.

### Paso 1: identifica tus dependencias reales (5 minutos)

Lista las librerías externas que tu proyecto necesita (lo que normalmente instalarías con `pip install`). Si todavía no tienes un `requirements.txt`, créalo ahora con esa lista, en `psets/proyecto/`, al lado del Dockerfile. Fija la versión de cada librería (`pandas==2.2.2`, no solo `pandas`), como el `requirements.txt` de la raíz del repositorio: sin versión, la imagen que construyas en un mes puede traer una librería distinta de la que probaste hoy.

_(tu lista de dependencias)_

### Paso 2: completa el Dockerfile (10 minutos)

Edita `psets/proyecto/Dockerfile`: resuelve cada `TODO`, decidiendo el orden de las instrucciones pensando en la cache (dependencias antes que código), y agrega un volumen en tus notas si tu proyecto lee o escribe datos.

### Paso 3: construye y verifica (5 minutos)

```
docker build -t <nombre-de-tu-proyecto> .
docker run <con -v si tu proyecto usa datos> <nombre-de-tu-proyecto>
```

Confirma que el resultado dentro del contenedor coincide con correr tu código directamente en tu máquina.

_(qué verificaste, y si encontraste alguna diferencia)_

## Antes de la próxima sesión

Ya tienes tu proyecto empaquetado en una imagen reproducible.

Pregunta: ¿qué pasa si necesitas provisionar el almacenamiento de datos donde ese contenedor va a leer y escribir, sin hacerlo a mano cada vez?

_(tu respuesta)_
