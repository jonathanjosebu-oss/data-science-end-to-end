# Ejercicio 2: imagen de resumir_clientes.py, con el mismo patron del
# Ejercicio 1. Corre bash comprobar.sh para revisar tu avance.

FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["python", "resumir_clientes.py"]
