# Semana 3, Sesión 2: Infraestructura como código para un pipeline de datos

> Objetivo de la sesión: levantar, con Docker Compose y con Terraform, la infraestructura de datos (Postgres y pgAdmin) que recibe un pipeline de ingesta, y explicar qué agrega Terraform sobre Docker Compose.

Hoy construimos juntos, en clase, la misma infraestructura dos veces: primero con Docker Compose, después con Terraform, sobre un dataset compartido (viajes de taxi de Nueva York, tres meses), no sobre tu proyecto individual. Sigue esta guía en vivo conmigo; cada paso trae el archivo completo, no solo el enunciado, para que te quede como referencia después de la sesión.

**Lectura previa de esta sesión:** ["What Is Infrastructure as Code (IaC)?"](https://www.ibm.com/think/topics/infrastructure-as-code), IBM Think.

**Referencia de esta sesión:** [Data Engineering Zoomcamp, Módulo 1 (DataTalksClub)](https://github.com/DataTalksClub/data-engineering-zoomcamp/tree/main/01-docker-terraform).

## Requisitos antes de esta sesión

1. **Docker**, el mismo de la sesión pasada. Verifica con `docker --version` y `docker compose version`.
2. **Terraform CLI:** en el Codespace ya viene instalado, verifica con `terraform -version`. En tu laptop, sigue la [guía oficial de instalación](https://developer.hashicorp.com/terraform/install).
3. **Al menos 2 GB libres de espacio en disco**, para las imágenes de Postgres, pgAdmin y Python que se descargan hoy (el Codespace ya tiene espacio de sobra).

A diferencia de la sesión de Terraform con Google Cloud de versiones anteriores de este curso, hoy no necesitas ninguna cuenta de nube ni credenciales: toda la infraestructura corre localmente, en tu propio Docker.

## Antes de empezar

A partir de la lectura previa:

**El artículo da un ejemplo: agregar una base de datos nueva por el método manual puede requerir un ticket al equipo de infraestructura y días de espera. ¿Qué reemplaza ese ticket y esa espera con infraestructura como código?**

_(tu respuesta)_

**Docker Compose ya describe el resultado final deseado en un archivo YAML declarativo. ¿Alcanza eso para llamarlo infraestructura como código completa, o falta algo? Anota tu intuición, la retomamos formalmente más adelante en la guía.**

_(tu respuesta)_

## Paso 1: Postgres y pgAdmin con Docker Compose

Crea `docker-compose.yml` en la raíz de esta carpeta:

```yaml
services:
  pg-database:
    image: postgres:13
    environment:
      POSTGRES_USER: taxi_user
      POSTGRES_PASSWORD: taxi_pass
      POSTGRES_DB: taxi_db
    ports:
      - "5432:5432"
    volumes:
      - datos_postgres:/var/lib/postgresql/data

  pgadmin:
    image: dpage/pgadmin4:9.18
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@example.com
      PGADMIN_DEFAULT_PASSWORD: admin123
    ports:
      - "8085:80"
    depends_on:
      - pg-database

volumes:
  datos_postgres:
```

pgAdmin queda en el puerto 8085, no en el 8080: ese puerto lo usa Kestra desde la Semana 4, y en el laboratorio integrador de la Semana 7 los dos corren al mismo tiempo.

**Respuesta 1, antes de correr `docker compose up`:** si quitáramos el bloque `volumes` de `pg-database` y detuviéramos los contenedores, ¿qué pasaría con los datos que hayamos cargado?

_(tu respuesta)_

**Respuesta 2:** dentro de pgAdmin, para conectarte a la base de datos, ¿qué valor va en el campo "Host": `localhost` o el nombre del servicio `pg-database`?

_(tu respuesta)_

Levanta los dos servicios:

```
docker compose up -d
```

Abre `localhost:8085` en el navegador (en el Codespace, desde la pestaña **Ports** de VS Code, puerto 8085), inicia sesión en pgAdmin con las credenciales de arriba, y registra un servidor nuevo apuntando a `pg-database` (no `localhost`), puerto 5432, usuario y contraseña de `POSTGRES_USER`/`POSTGRES_PASSWORD`. Confirma que ves la base `taxi_db`, todavía vacía.

## Paso 2: agregar la ingesta

Los archivos de partida de esta sesión (`starter/ingest_data.py`, `starter/Dockerfile`, `starter/requirements.txt`) ya están construidos: el script descarga tres meses de datos de taxis amarillos de Nueva York (enero a marzo de 2023) desde la fuente pública de la TLC y carga los primeros 300.000 viajes de cada mes en Postgres, usando el mismo patrón de `Dockerfile` (`FROM`, `WORKDIR`, `COPY`, `RUN`, `CMD`) de la sesión pasada. Cópialos a la raíz de esta carpeta, junto a `docker-compose.yml`.

Agrega el tercer servicio al archivo:

```yaml
  ingesta:
    build: .
    environment:
      PG_HOST: pg-database
      PG_PORT: 5432
      PG_DATABASE: taxi_db
      PG_USER: taxi_user
      PG_PASSWORD: taxi_pass
      PG_TABLE: viajes_taxi
    depends_on:
      - pg-database
```

**Respuesta, antes de correr nada:** `depends_on` hace que Docker Compose arranque `pg-database` antes que `ingesta`. ¿Eso garantiza que Postgres ya acepta conexiones en el momento exacto en que el script de ingesta intenta conectarse? Anota tu intuición, la respuesta llega en clase antes de correr el comando.

_(tu respuesta)_

Corre:

```
docker compose up --build
```

Sigue los logs del contenedor `ingesta`: si Postgres todavía no está listo, reintenta la conexión; después descarga y carga los tres meses (uno o dos minutos). Cuando termine, en pgAdmin, abre la herramienta de consultas sobre `taxi_db` y corre:

```sql
SELECT mes_origen, COUNT(*) FROM viajes_taxi GROUP BY mes_origen ORDER BY mes_origen;
```

_(cuántas filas viste por mes)_

## Durante el ConcepTest

Pregunta: si Terraform ya creó los tres contenedores y alguien detiene `pg-database` manualmente con `docker stop`, ¿qué muestra `terraform plan` al correrlo después?

**Tu voto, antes de discutir en pareja** (A, B, C o D):

_(tu voto)_

**Tu razonamiento:**

_(tu respuesta)_

**Después de discutir en pareja, ¿cambiaste de voto? ¿Por qué?**

_(tu respuesta)_

## Paso 3: el mismo resultado con Terraform

Antes de escribir nada, apaga y borra por completo lo que Compose creó, para que Terraform parta de cero:

```
docker compose down -v
```

Crea `terraform/main.tf`:

```hcl
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 4.0"
    }
  }
}

provider "docker" {}

resource "docker_network" "red_taxis" {
  name = "red-taxis"
}

resource "docker_volume" "datos_postgres" {
  name = "datos-postgres"
}

resource "docker_image" "postgres" {
  name = "postgres:13"
}

resource "docker_image" "pgadmin" {
  name = "dpage/pgadmin4:9.18"
}

resource "docker_image" "ingesta" {
  name = "demo-taxis-ingesta:local"
  build {
    context = "${path.module}/../"
  }
}

resource "docker_container" "pg_database" {
  name  = "pg-database"
  image = docker_image.postgres.image_id

  env = [
    "POSTGRES_USER=taxi_user",
    "POSTGRES_PASSWORD=taxi_pass",
    "POSTGRES_DB=taxi_db",
  ]

  ports {
    internal = 5432
    external = 5432
  }

  volumes {
    volume_name    = docker_volume.datos_postgres.name
    container_path = "/var/lib/postgresql/data"
  }

  networks_advanced {
    name    = docker_network.red_taxis.name
    aliases = ["pg-database"]
  }
}

resource "docker_container" "pgadmin" {
  name  = "pgadmin"
  image = docker_image.pgadmin.image_id

  env = [
    "PGADMIN_DEFAULT_EMAIL=admin@example.com",
    "PGADMIN_DEFAULT_PASSWORD=admin123",
  ]

  ports {
    internal = 80
    external = 8085
  }

  networks_advanced {
    name = docker_network.red_taxis.name
  }

  depends_on = [docker_container.pg_database]
}

resource "docker_container" "ingesta" {
  name  = "ingesta"
  image = docker_image.ingesta.image_id

  # La ingesta carga los datos y termina. Sin esto, Terraform espera que el
  # contenedor siga corriendo y cada plan propone volver a arrancarlo.
  must_run = false

  env = [
    "PG_HOST=pg-database",
    "PG_PORT=5432",
    "PG_DATABASE=taxi_db",
    "PG_USER=taxi_user",
    "PG_PASSWORD=taxi_pass",
    "PG_TABLE=viajes_taxi",
  ]

  networks_advanced {
    name = docker_network.red_taxis.name
  }

  depends_on = [docker_container.pg_database]
}
```

Compara cada bloque contra su equivalente de `docker-compose.yml`: `docker_network` y `docker_volume` son la red y el volumen que en Compose quedaban implícitos; cada `docker_container` trae los mismos `env`, `ports` y `volumes` que su servicio, más `networks_advanced` y `depends_on` explícitos, porque Terraform no asume ninguna relación que no esté escrita. `must_run = false` en la ingesta le dice a Terraform que ese contenedor termina cuando acaba la carga, y que no está roto por estar detenido.

Aplica:

```
cd terraform
terraform init
terraform plan
terraform apply
```

Revisa `terraform plan` antes de confirmar el `apply`: ¿coincide con lo que esperabas crear? `docker compose down -v` borró el volumen de Compose, así que Terraform parte con un volumen nuevo y vacío, y su contenedor de ingesta vuelve a cargar los tres meses. Cuando termine (`docker logs -f ingesta`), verifica en pgAdmin (regístrala de nuevo si hace falta) que están los 900.000 viajes, esta vez en la infraestructura que levantó Terraform. Después corre `terraform plan` otra vez: con todo ya creado, ¿qué esperas que diga?

_(qué mostró tu `terraform plan`, y qué verificaste en pgAdmin)_

Al final de la sesión, para no dejar contenedores corriendo:

```
terraform destroy
```

## Antes de la próxima sesión

Ya tienes la infraestructura de datos levantada y el pipeline de ingesta corriendo una vez.

Pregunta: ¿cómo te aseguras de que ese pipeline corra solo, todos los días, sin que alguien tenga que acordarse de correrlo a mano?

_(tu respuesta)_
