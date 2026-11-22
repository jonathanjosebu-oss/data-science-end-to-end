FROM python:3.11-slim

RUN pip install --no-cache-dir dbt-core==1.11.6 dbt-snowflake==1.11.4

# El proyecto se copia en la imagen; el perfil solo lee variables de entorno,
# así no hay credenciales dentro de la imagen.
WORKDIR /opt/dbt
COPY dbt_project.yml ./
COPY macros ./macros
COPY models ./models
COPY tests ./tests
COPY profiles.yml.example ./profiles/profiles.yml
ENV DBT_PROFILES_DIR=/opt/dbt/profiles
# Sin ENTRYPOINT: Kestra (DbtCLI) ejecuta sus comandos con /bin/sh -c.
CMD ["dbt", "build"]
