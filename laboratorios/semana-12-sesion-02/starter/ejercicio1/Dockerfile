# La imagen del servicio: el mismo patron de la Semana 3 (dependencias antes
# que codigo), con el modelo ya entrenado adentro. Antes de construirla,
# corre python entrenar.py para que exista modelo_tarifa.joblib.
#
#     docker build -t servicio-tarifa .
#     docker run -p 8000:8000 servicio-tarifa
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY preparacion_taxis.py features_taxis.py servicio.py modelo_tarifa.joblib ./
EXPOSE 8000

# TODO 5: el comando que levanta el servicio con uvicorn en el puerto 8000,
# escuchando en todas las interfaces del contenedor (host 0.0.0.0).
CMD ["uvicorn", "servicio:app", "--port", "8000"]
