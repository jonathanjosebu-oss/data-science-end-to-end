# Fundamentos de Ciencia de Datos

Repositorio base del curso.

Aquí viven los laboratorios y los PSets, construidos en torno a un único proyecto de ciencia de datos que cada estudiante define y lleva a cabo de principio a fin durante la clase. Es la fuente de la verdad: todo tu trabajo del semestre va aquí, no en otro lado.

## Antes de empezar

No clones ni hagas push a este repositorio directamente. Cada estudiante trabaja en su propio fork:

1. Arriba a la derecha, haz clic en **"Fork"** y créalo en tu propia cuenta de GitHub.
2. Todo tu trabajo del semestre (laboratorios, PSets) va en tu fork, no aquí.

## Tu ambiente de desarrollo

Las primeras dos semanas del curso son de formulación y diseño del proyecto: no requieren código. Desde la Semana 3, cada laboratorio usa herramientas que se instalan una sola vez: Python, Docker, Terraform, Java (para Spark), DuckDB, dbt, Jupyter y las librerías fijadas en [`requirements.txt`](./requirements.txt). Tienes dos opciones, y las dos llegan exactamente al mismo ambiente.

### Opción A (recomendada): GitHub Codespaces

Un Codespace es una máquina en la nube con VS Code en el navegador, ya configurada con todo lo del curso. No instalas nada en tu laptop, y funciona igual en Windows, Mac o Linux.

1. Activa [GitHub Education](https://education.github.com/pack) con tu correo de la universidad. Es gratis y sube tu cuota mensual de Codespaces.
2. En la página de tu fork, haz clic en **"Code" → pestaña "Codespaces" → "Create codespace on master"**.
3. La primera vez tarda varios minutos: instala todo y al final corre una verificación ([`.devcontainer/verificar.sh`](./.devcontainer/verificar.sh)). Cuando la terminal muestre `Ambiente listo.`, ya puedes trabajar. Si algo deja de funcionar más adelante, vuelve a correr `bash .devcontainer/verificar.sh` para ver qué herramienta falla. Las siguientes veces abre el mismo Codespace desde [github.com/codespaces](https://github.com/codespaces), no crees uno nuevo.

Cinco reglas para no quedarte sin cuota ni perder trabajo:

- **Detén el Codespace al terminar** (desde [github.com/codespaces](https://github.com/codespaces), menú "..." → "Stop codespace"). Se apaga solo después de 30 minutos sin actividad, pero consume cuota hasta entonces. La cuota gratuita equivale a unas 60 horas al mes en una máquina de 2 núcleos (unas 90 con GitHub Education): alcanza para el curso solo si lo apagas.
- **Haz commit y push seguido.** Un Codespace sin usar durante 30 días se borra con todo lo que no hayas subido a tu fork.
- **Tus datos no se suben a git** (`data/raw/` y `data/processed/` están en `.gitignore`). Guarda la fuente original de tu dataset fuera del Codespace (el enlace de descarga, o una copia en tu Drive), para poder volver a traerlo si el Codespace se borra.
- **Usa una máquina de 4 núcleos solo cuando el laboratorio lo pida.** Kestra (Semana 4, Sesión 1) y el laboratorio integrador (Semana 7, Sesión 1) levantan varios servicios a la vez; ahí cambia el tipo de máquina ("Change machine type"). El resto del curso funciona con 2 núcleos, que gasta la mitad de la cuota.
- **Las interfaces web no se abren en el `localhost` de tu navegador.** pgAdmin (puerto 8085), Kestra (puerto 8080) y MLflow (puerto 5050) corren dentro del Codespace: ábrelas desde la pestaña **Ports** de VS Code, con el ícono del globo junto al puerto. MLflow se levanta solo cada vez que inicia el Codespace (si no responde, `bash .devcontainer/mlflow-server.sh` lo vuelve a levantar). pgAdmin y Kestra aparecen en Ports solo mientras el laboratorio que los usa los tiene levantados con `docker compose`.

### Opción B: tu propia laptop

Instala [Docker Desktop](https://www.docker.com/products/docker-desktop/), [Terraform](https://developer.hashicorp.com/terraform/install), Java 17 y Python 3.11, y después, desde la raíz de tu fork:

```
pip install -r requirements.txt
```

Si ya tienes Docker Desktop y VS Code con la extensión Dev Containers, hay un atajo: abre tu fork en VS Code y elige "Reopen in Container". Usa la misma configuración del Codespace, pero corriendo en tu máquina.

### El Codespace es un contenedor, y no reemplaza al de tu proyecto

El Codespace trae las herramientas del curso, iguales para todos. Tu proyecto, en cambio, se empaqueta en su propia imagen de Docker (Semana 3, Sesión 1), con solo lo que necesita para correr en cualquier máquina. Son dos cosas distintas, y el curso necesita las dos.

## Infraestructura del curso: qué se levanta y cuándo

Lo único que corre siempre es MLflow. El resto son servicios que cada laboratorio levanta con `docker compose` cuando los necesita, como en un proyecto: cada servicio se declara en un archivo, se levanta para trabajar y se apaga al terminar. DuckDB, dbt y Spark no son servicios: son librerías que ya vienen instaladas y corren dentro de tu script.

| Componente | Semanas | Cómo se levanta | Dónde se ve |
|---|---|---|---|
| Postgres + pgAdmin | 3 (Sesión 2) y 7 | `docker compose up -d` con el `docker-compose.yml` que escribes en el Paso 1 de [`semana-03-sesion-02`](./laboratorios/semana-03-sesion-02/README.md), o `terraform apply` con el `main.tf` de la misma sesión | pgAdmin en el puerto 8085 (`admin@example.com` / `admin123`); Postgres en el 5432 |
| Kestra (con su propio Postgres) | 4 (Sesión 1) y 7 | `docker compose up -d` desde [`semana-04-sesion-01/starter/`](./laboratorios/semana-04-sesion-01/starter/docker-compose.yml). Pide máquina de 4 núcleos | Puerto 8080 (`admin@kestra.io` / `Admin1234`) |
| Redpanda (Kafka) | 6 (Sesión 2) y 7, si tu proyecto usa streaming | `docker compose up -d` desde [`semana-06-sesion-02/starter/`](./laboratorios/semana-06-sesion-02/starter/docker-compose.yml) | Puerto 9092, sin interfaz web: se usa desde Python |
| MLflow | 11 en adelante | Se levanta solo al iniciar el Codespace. Si no responde: `bash .devcontainer/mlflow-server.sh` | Puerto 5050 |

Para apagar un servicio, corre `docker compose down` en la misma carpeta desde donde lo levantaste. Sin `-v`, los datos guardados en volúmenes (tus flows de Kestra, tus tablas de Postgres) se conservan para la próxima vez; con `-v`, se borran. Con Terraform, el equivalente es `terraform destroy`, que sí borra todo lo que creó.

`docker ps` muestra qué está corriendo en este momento. Si el Codespace se pone lento, revisa ahí: con 2 núcleos, Kestra y Redpanda levantados a la vez no caben. Cuando el Codespace se detiene, todos los contenedores se apagan con él y no vuelven a arrancar solos; MLflow sí, porque lo levanta el Codespace.

## Notebooks y scripts

El curso usa los dos, y cada laboratorio dice cuál. El criterio es el mismo de un equipo de datos en una empresa:

- **Notebook (`.ipynb`)** cuando el resultado es algo que lees para decidir: diagnosticar la calidad de un dataset, explorarlo, probar features, comparar modelos. La tabla o el gráfico queda debajo del código que lo produjo, y puedes volver a correr una sola celda sin repetir todo lo anterior.
- **Script (`.py`)** cuando el resultado tiene que correr sin nadie mirando: lo que ejecuta un contenedor, una tarea de Kestra, un job de Spark, el pipeline de preparación que importan otros archivos, un servicio de predicción.

El paso de uno a otro también se practica: lo que decides en tu notebook de diagnóstico (Semana 4) pasa a un script de limpieza (Semana 7), y las features que pruebas en tu notebook (Semana 9, Sesión 1) pasan a `pipeline_proyecto.py`, que tus notebooks de modelos importan en vez de copiar el código (Semana 9, Sesión 2, en adelante).

Para abrir un notebook en el Codespace, haz clic en el archivo `.ipynb`. La primera vez, VS Code pide un kernel ("Select Kernel"): elige **Python Environments** y después **Python 3.11** (`/usr/local/bin/python`), el Python que tiene instaladas las librerías del curso. En tu laptop sin VS Code, corre `jupyter lab` desde la raíz de tu fork.

Antes de hacer commit de un notebook, reinicia el kernel y corre todo (**Restart** y después **Run All**). Un notebook muestra lo que produjo cada celda la última vez que la corriste, aunque haya sido en otro orden o con una variable que ya borraste; reiniciar y correr todo comprueba que lo que subes funciona de principio a fin.

## Pruebas e integración continua

Desde la Semana 12, el código de tu proyecto que corre sin nadie mirando (la preparación, el servicio de predicción) tiene pruebas automáticas con pytest. GitHub Actions las corre en cada push, en una máquina limpia, con el workflow de [`.github/workflows/pruebas.yml`](./.github/workflows/pruebas.yml), y marca cada commit con un check verde o una X roja. En tu fork, Actions viene apagado: actívalo una vez desde la pestaña **Actions** de tu fork. Para correr las mismas pruebas en el Codespace, desde la raíz:

```
pytest psets/proyecto -v
```

## Estructura del repositorio

```
.devcontainer/          Configuración del Codespace (no la modifiques)
.github/workflows/      Integración continua: corre las pruebas de psets/proyecto en cada push
requirements.txt        Librerías de Python del curso, con versión fija
laboratorios/           Laboratorio de cada clase, uno por carpeta
  semana-01-sesion-02/
  ...
  semana-12-sesion-02/
psets/
  README.md             Cómo se organiza tu proyecto y cómo se entrega cada PSet
  pset-01/ ... pset-04/ Enunciado y rúbrica de cada PSet
  proyecto/             Tu proyecto: lo construyes aquí durante todo el semestre
```

Cada carpeta de `laboratorios/` tiene su propio `README.md` con las instrucciones de esa sesión. Los Ejercicios 1 y 2 de cada laboratorio se resuelven dentro de su carpeta; el Ejercicio 3, sobre tu proyecto, va en `psets/proyecto/`, en la carpeta que indica el laboratorio. [`psets/README.md`](./psets/README.md) explica la estructura del proyecto y qué carpeta califica cada PSet.

## Cómo actualizar tu fork cada semana

Cuando se agregue una semana nueva, sincroniza tu fork:

1. En la página de tu fork en GitHub, haz clic en el botón **"Sync fork" → "Update branch"**.
2. En tu copia local o en tu Codespace, ejecuta `git pull` para obtener esos cambios.
3. Si el cambio tocó `requirements.txt`, corre `pip install -r requirements.txt`. Si tocó `.devcontainer/`, reconstruye el contenedor: en VS Code, `Ctrl+Shift+P` (`Cmd+Shift+P` en Mac) → "Codespaces: Rebuild Container" (o "Dev Containers: Rebuild Container" en tu laptop).

Por terminal, en vez del botón:
```
git fetch upstream
git merge upstream/master
```
(la primera vez, agrega el remoto: `git remote add upstream https://github.com/ErickNaunay/fundamentos-ciencia-datos.git`)

## Cómo trabajar aquí

- Haz commits de tu avance de forma continua, con mensajes que indiquen qué hiciste, no `"cambios"` ni `"fix"`.
- Cada entrega (laboratorio, PSet) tiene su propia carpeta con su propio `README.md`: revísalo antes de empezar.
