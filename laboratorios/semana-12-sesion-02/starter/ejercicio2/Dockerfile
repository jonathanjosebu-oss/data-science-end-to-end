# La imagen del servicio: el mismo patron de la Semana 3 (dependencias antes
# que codigo), con el modelo ya entrenado adentro. Antes de construirla,
# corre python entrenar_fraude.py para que exista modelo_fraude.joblib.
#
#     docker build -t servicio-fraude .
#     docker run -p 8000:8000 servicio-fraude
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY preparacion_pagos.py servicio_fraude.py modelo_fraude.joblib ./
EXPOSE 8000

CMD ["uvicorn", "servicio_fraude:app", "--host", "0.0.0.0", "--port", "8000"]
