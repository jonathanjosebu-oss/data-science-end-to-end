# Tu proyecto y sus cuatro PSets

Durante el semestre construyes un solo proyecto de ciencia de datos, y cada PSet entrega la siguiente etapa del mismo proyecto. El código, los datos y los documentos viven en una sola carpeta, [`proyecto/`](./proyecto/), organizada como la organizaría un equipo de datos: cualquiera que clone tu fork encuentra cada pieza en el mismo lugar. Las carpetas `pset-01/` a `pset-04/` traen el enunciado y la rúbrica de cada entrega; tu trabajo no va ahí, va en `proyecto/`.

| PSet | Qué entrega | Semanas | Se asigna | Vence | Dónde queda en `proyecto/` |
|---|---|---|---|---|---|
| [PSet 1](./pset-01/README.md) | Propuesta del proyecto y su ambiente | 1 a 3 | Semana 2, Sesión 2 | Semana 4, Sesión 1 | `docs/`, `Dockerfile`, `requirements.txt`, `ingesta/`, `infra/` |
| [PSet 2](./pset-02/README.md) | Pipeline de datos | 4 a 6, cerrado en la 7 | Semana 4, Sesión 1 | Semana 7, Sesión 2 | `orquestacion/`, `calidad/`, `warehouse/`, `procesamiento/` |
| [PSet 3](./pset-03/README.md) | Exploración, features y modelo entrenado y trackeado | 8 (Sesión 2) a 11 | Semana 8, Sesión 2 | Semana 12, Sesión 1 | `modelado/` y `docs/decision_modelo.md` |
| [PSet 4](./pset-04/README.md) | Despliegue, monitoreo y comunicación del modelo | 12 a 15 (Sesión 1) | Semana 12, Sesión 1 | Semana 15, Sesión 2 | `servicio/`, `monitoreo/` y `docs/` |

En la Semana 16, Sesión 1 presentas el proyecto completo, tal como quedó en el PSet 4.

Los cuatro PSets valen en conjunto 25% de la nota final, 6.25% cada uno.

## La estructura de `proyecto/`

```
proyecto/
  README.md              Qué resuelve tu proyecto y cómo se corre de principio a fin
  Dockerfile             La imagen de tu proyecto (Semana 3, Sesión 1), la que corre Kestra
  requirements.txt       Las librerías de tu proyecto, no las del curso
  .dockerignore          Lo que no entra a ninguna imagen (los datos llegan con un volumen)
  conftest.py            Deja psets/proyecto/ en la ruta de las pruebas (no lo modifiques)
  docs/                  Propuesta (PSet 1), decisión del modelo (PSet 3), despliegue, comunicación y retirada (PSet 4)
  data/
    raw/                 Lo que trae tu ingesta, sin tocar (no se sube a git)
    processed/           Lo que deja tu limpieza, listo para cargar y modelar (no se sube a git)
  ingesta/               El script que trae los datos (Semanas 3 y 4)
  infra/                 docker-compose.yml o main.tf de tu base de datos (Semanas 3 y 7)
  orquestacion/          El flow de Kestra (Semana 4, Sesión 1)
  calidad/               Notebook de diagnóstico (Semana 4, Sesión 2) y script de limpieza (Semana 7)
  warehouse/             Carga a DuckDB (Semana 5, Sesión 1) y proyecto de dbt en dbt/ (Semana 5, Sesión 2)
  procesamiento/         Job de Spark (Semana 6, Sesión 1); productor y consumidor (Semana 6, Sesión 2), si tu proyecto usa streaming
  modelado/              Exploración, features y pipeline_proyecto.py (Semanas 8 y 9); modelos, experimentos y validación (Semanas 10 y 11)
  servicio/              El modelo como servicio de predicción, con sus pruebas y su propio Dockerfile (Semana 12)
  monitoreo/             Métricas del servicio y simulación de deriva (Semanas 13 y 14)
```

Cada laboratorio dice en qué carpeta va lo que produce su Ejercicio 3. Dos carpetas mezclan notebooks y scripts a propósito: en `calidad/`, el notebook donde diagnosticas queda al lado de `limpiar.py`, el script que aplica lo que decidiste; en `modelado/`, los notebooks quedan al lado de `pipeline_proyecto.py` para importarlo (`from pipeline_proyecto import ...`) sin copiar su código.

Desde la Semana 12, cada pieza de código tiene sus pruebas al lado (`modelado/test_pipeline_proyecto.py`, `servicio/test_api.py`), y GitHub Actions las corre en cada push con `pytest psets/proyecto` (el workflow está en [`.github/workflows/pruebas.yml`](../.github/workflows/pruebas.yml); en tu fork se activa una vez desde la pestaña **Actions**). Las pruebas arman sus propios datos de pocas filas: no leen `data/`, que no se sube.

Las rutas a los datos se escriben relativas a la carpeta del archivo que las usa: desde `modelado/` o `calidad/`, tu archivo limpio es `../data/processed/<archivo>`. Los notebooks corren con su propia carpeta como directorio de trabajo, y los scripts se corren desde su carpeta (`cd psets/proyecto/calidad && python limpiar.py`).

## Lo que no se sube

Tus datos no se suben a git: `data/raw/` y `data/processed/` están en `.gitignore`, igual que los archivos `.duckdb` y el registro de MLflow. En su lugar, la sección "Datos" de `proyecto/README.md` dice de dónde salen y con qué comando se regeneran. Las contraseñas tampoco se suben: si tu ingesta usa una API con clave, la clave va en un archivo `.env` que no se sube, y el código la lee con `os.environ`.

## Cómo entregar

Haz commit y push de tu trabajo, y marca la entrega con un tag de git desde la raíz de tu fork:

```
git tag pset-02
git push origin pset-02
```

Califico el proyecto tal como quedó en ese tag. Como el proyecto sigue creciendo después de cada entrega, el tag deja fija la versión que corresponde a cada PSet: lo que cambies después cuenta para el siguiente, no para este. Si necesitas corregir algo antes de la fecha de entrega, mueve el tag con `git tag -f pset-02` y `git push -f origin pset-02`.

Antes de marcar el tag, reinicia el kernel y corre todo (**Restart** y después **Run All**) en cada notebook de la entrega, y comprueba que cada script corre desde una terminal nueva.
