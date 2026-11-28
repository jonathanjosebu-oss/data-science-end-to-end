# Guion del video de demostración (máximo 7 minutos)

El video termina en el mismo estado que documenta el memo: el champion es el
**v5**. El reentrenamiento en vivo aprueba un **v6** y después el rollback
vuelve al v5, así se demuestran las dos cosas.

## Preparación (fuera de cámara)

1. Servicios arriba: `docker compose ps` muestra kestra, mlflow, api, spark y tablero.
2. Pestañas de Chrome, en este orden:
   1. Kestra `http://localhost:8080` (con la sesión ya iniciada)
   2. MLflow `http://localhost:5000/#/models/qsrr-predict-modelo`
   3. API `http://localhost:8000/docs`
   4. Tablero `http://localhost:8501`
3. Tener el `ADMIN_TOKEN` en un bloc de notas **fuera de la pantalla**. No mostrar el `.env`.
   - Al pegarlo en `x-admin-token` (bloques 4, 5 y 7) el token **sí se ve** en el video.
     Por eso se cambia al terminar de grabar (ver "Después de grabar").
4. El reentrenamiento `semana = 11` ya debe estar en **PAUSED**.
   - Se lanza en Kestra → Flows → `reentrenamiento` → Execute, con `motivo = manual: demostración del ciclo`.
   - En la ejecución preparada, la regla compara v5 y v6 en el lote 10: 8,151 frente a 6,102 min, y recomienda promover.
5. Zoom de Chrome en 110–125 %, notificaciones apagadas y grabación en 1080p.

Cada bloque se graba como un clip separado. Lo que está entre comillas se dice
con tus palabras; no hace falta leerlo literal.

---

## Bloque 1 · Presentación e infraestructura (0:00–0:40)

**Hacer:**
1. Terminal en `proyecto_final/`.
2. Escribir `docker compose up -d`.
3. Escribir `docker compose ps`.

**Decir:**
> "Hola, soy Jonatan Buenaño. Este es QSRR-Predict, un sistema que predice el tiempo de retención de compuestos en HPLC para decidir si un método se puede aprobar sin una corrida exploratoria.
> Todo el sistema se levanta con un solo comando: `docker compose up -d`. Aquí están los servicios: Kestra para orquestar, Spark para construir la tabla de modelado, MLflow para el registro de modelos, la API con FastAPI y el tablero de monitoreo en Streamlit. Los datos viven en Snowflake."

---

## Bloque 2 · Ingesta hasta la OBT (0:40–1:40)

**Hacer:**
1. Kestra → Flows → `ingesta`, y mostrar el código del flujo unos segundos.
2. Execute con los valores por defecto y mostrar que arranca.
3. **Cortar la espera, que dura unos 3 min.** Abrir una ejecución de `ingesta` terminada en verde → pestaña **Gantt**.
4. Señalar las tareas en orden: descarga, carga a RAW, `dbt_build`, `spark_obt`.

**Decir:**
> "La ingesta corre cada semana. Descarga RepoRT, guarda el commit de origen y publica una partición por fecha en la capa RAW de Snowflake.
> Luego dbt construye Bronze, Silver y Gold, con 46 pruebas de calidad: rangos, conservación de filas entre capas y relaciones.
> Al final Spark valida que las claves sean únicas y que no haya hechos huérfanos **antes** de escribir la OBT. Si algo falla, no escribe nada.
> En el Gantt se ve cada paso con su duración, y si un paso falla, el bloque de errores limpia lo que quedó a medias."

---

## Bloque 3 · Predicción válida e inválida (1:40–2:40)

**Hacer:**
1. Pestaña API `/docs` → `GET /modelo` → Try it out → Execute. Señalar `"version": 5` y el `run_id`.
2. `POST /predecir` → Try it out, dejar el ejemplo → Execute.
3. Señalar `decision`, los tiempos predichos, `version_modelo` y `run_id`.
4. En el cuerpo, borrar la línea de `tipo_columna` (cuidar la coma) → Execute. Señalar el **422** con `"campo": "tipo_columna"`.

**Decir:**
> "La API siempre carga el modelo que tiene el alias champion en MLflow, hoy la versión 5. La imagen de Docker no contiene el modelo.
> Envío un método con dos compuestos. La respuesta trae la decisión, aquí 'revisar condiciones', el tiempo predicho de cada compuesto y la versión y el run del modelo que la produjo. Cada predicción queda registrada y se puede rastrear hasta los datos de entrenamiento.
> Si quito un campo obligatorio, la API responde 422 y dice exactamente qué campo falta. La validación replica la firma del modelo."

---

## Bloque 4 · Reentrenamiento con aprobación humana (2:40–4:10)

**Hacer:**
1. Kestra → Executions → la ejecución de `reentrenamiento` en **PAUSED**.
2. Mostrar el Gantt: `entrenar_challenger` y `comparar` en verde, `aprobacion` en pausa.
3. Logs → buscar "RMSE lote 10" y señalar la línea: `champion v5 8.151 vs challenger v6 6.102 … la regla RECOMIENDA promover`.
4. Botón **Resume** → `aprobar = true`, motivo: `mejora de 2 min en el lote 10` → confirmar.
5. Esperar a que `decidir` termine en verde. **Cortar esta espera en la edición.**
6. Pestaña MLflow → refrescar: el alias **champion** está en la **versión 6**.
7. Pestaña API → `POST /admin/recargar` con el token → Execute, y luego `GET /modelo` → Execute. Señalar `"version": 6`.
   No esperar los 30 s del caché en cámara: el bloque solo tiene 1:30.

**Decir:**
> "El monitoreo dispara un reentrenamiento cuando hay dos lotes seguidos con alerta de desempeño, o cada ocho lotes por calendario. Aquí lo lancé de forma manual para la demostración.
> El flujo entrena un challenger con todo el histórico más los lotes ya etiquetados y lo registra en MLflow como versión 6. Luego lo compara con el champion en el lote más reciente: el error baja de 8,15 a 6,10 minutos, mucho más que una desviación estándar de la validación cruzada, así que la regla recomienda promover.
> Pero el flujo no promueve solo: se detiene hasta que una persona decide. Apruebo y escribo el motivo.
> Al aprobar, el alias champion se mueve a la versión 6 y la API toma el modelo nuevo en unos 30 segundos, sin reconstruir ni reiniciar el contenedor.
> En la simulación también hubo un challenger rechazado en la semana 8, porque mejoraba solo 0,03 minutos."

---

## Bloque 5 · Rollback (4:10–5:00)

**Hacer:**
1. MLflow → modelo `qsrr-predict-modelo` → **Version 5** → Aliases → agregar `champion` → guardar. MLflow lo quita del v6.
2. Volver a la lista de versiones y mostrar `champion` en la versión 5.
3. API → `GET /modelo`, o `POST /admin/recargar` con el token. Señalar `"version": 5`.

**Decir:**
> "Si el modelo nuevo se comporta mal en producción, volver atrás es mover el alias. Lo regreso a la versión 5.
> La API vuelve a la versión 5 en menos de un minuto, sin tocar Docker. Las versiones anteriores nunca se borran del registro."

---

## Bloque 6 · El lote con deriva dispara la alerta (5:00–6:05)

**Hacer:**
1. Kestra → Flows → `monitoreo` → Execute con `semana = 8`. Tarda unos 40 s.
2. Logs → señalar `[ALERTA ALTA] … desempeno_rmse` y `desempeno_sesgo · deriva conceptual`.
3. Pestaña Tablero → **Desempeño y negocio**: círculos rojos desde el lote 6 y líneas grises de los reentrenamientos.
4. Si da tiempo, mostrar la pestaña **Deriva y datos** (PSI por lote).

**Decir:**
> "Para probar el monitoreo simulamos 11 semanas de producción con lotes de laboratorios nuevos. Desde el lote 6 inducimos un cambio de equipo: un HPLC con 1 mL más de volumen de retardo, así que los picos salen más tarde.
> El monitoreo compara cada lote con sus etiquetas. Los umbrales se calibraron con el propio entrenamiento: RMSE mayor a 3,66 minutos o sesgo mayor a 1,81.
> En la semana 8 aparecen la alerta de error y la de sesgo, con el diagnóstico de deriva conceptual: las entradas no cambiaron, cambió la relación entre las entradas y el tiempo.
> En el tablero se ve el antes y el después: los lotes 1 a 5 no generan alertas de desempeño, y desde el 6 aparecen los círculos rojos y las líneas de reentrenamiento."

---

## Bloque 7 · Interruptor de respaldo (6:05–6:45)

**Hacer:**
1. API `/docs` → `POST /admin/respaldo` → Try it out → `activo = true`, **sin** token → Execute → **403**.
2. Pegar el token en `x-admin-token` → Execute → `"respaldo_activo": true`.
3. `POST /predecir` con el ejemplo → señalar `"respaldo_usado": true`.
4. `POST /admin/respaldo` con `activo = false` y el token → `"respaldo_activo": false`.

**Decir:**
> "Si el modelo falla o hay que retirarlo, un interruptor protegido con token pasa la API a la regla de negocio, la mediana histórica por condición. Sin token responde 403.
> Con el token lo activo, y la predicción indica que usó el respaldo. El analista sigue trabajando. Lo desactivo y vuelve el modelo."

---

## Cierre (6:45–7:00)

**Hacer:** mostrar la pestaña **Sistema** del tablero o la diapositiva de recomendación.

**Decir:**
> "En resumen: el sistema detecta el cambio, alerta y se actualiza con aprobación humana. Todavía no ahorra corridas, porque incluso sin deriva, con un error de 2 a 3 minutos, no distingue los picos que se solapan. Por eso la recomendación es ajustarlo con una calibración por método y un piloto de tres meses antes de escalarlo. Gracias."

---

## Si algo sale distinto

- **`/modelo` no cambia:** el caché dura 30 s. Usa `POST /admin/recargar` con el token.
- **La ingesta tarda:** no esperes en cámara; muestra una ejecución terminada.
- **Te equivocas al hablar:** pausa 2 segundos, repite la frase y corta en la edición.
- **El Resume falla o lo pulsaste antes de grabar:** avísame y lanzo otro reentrenamiento (tarda unos 4 min).

## Después de grabar

Primero cambiar el token, porque quedó visible en el video:
1. En `.env`, poner un valor nuevo en `ADMIN_TOKEN`.
2. Reiniciar la API: `docker compose up -d api`.
3. Probar `POST /admin/respaldo` con el token anterior: debe responder **403**.

Subir el video como YouTube no listado o en Drive con acceso por enlace, y pasar el enlace para:
`python -m scripts.exportar_evidencia` (incluye el ciclo del v6) y
`python -m scripts.construir_memo --video <URL>`.
