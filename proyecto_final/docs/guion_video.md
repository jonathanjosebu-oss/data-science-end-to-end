# Guion del video de demostración (máximo 7 minutos)

Orden pensado para terminar en el mismo estado que documenta el memo: el
champion es el **v5**. El reentrenamiento en vivo crea un **v6**, se aprueba y
después el rollback vuelve al v5, de modo que se demuestran ambas cosas.

## Preparación (antes de grabar, fuera de cámara)

1. Infraestructura arriba: `docker compose ps` (kestra, mlflow, api, spark, tablero).
2. Abrir en pestañas: Kestra `localhost:8080`, MLflow `localhost:5000/#/models/qsrr-predict-modelo`,
   API `localhost:8000/docs`, tablero `localhost:8501`.
3. Tener a mano el `ADMIN_TOKEN` del `.env` (no mostrar el `.env` en el video).
4. **Unos 6 minutos antes del bloque 4**, lanzar el reentrenamiento para que ya esté en la pausa:
   Kestra → Flows → `reentrenamiento` → Execute → `semana = 11`,
   `motivo = manual: demostración del ciclo`. Tarda unos 4 min en entrenar y comparar.
5. Grabar a 1080p, con la ventana del navegador maximizada y el zoom en 110–125 %.

## Bloques

| Tiempo | Bloque | Qué hacer en pantalla | Qué decir (idea) |
|---|---|---|---|
| 0:00–0:35 | 1. Infraestructura | Terminal en `proyecto_final/`: `docker compose up -d` y `docker compose ps` | "Un solo comando levanta Kestra, Spark, MLflow, la API y el tablero." |
| 0:35–1:35 | 2. Ingesta hasta la OBT | Kestra → `ingesta` → Execute (por defecto). Mostrar que arranca y abrir una ejecución terminada → pestaña **Gantt**: descarga, carga a RAW, `dbt build`, `spark_obt` | "Descarga RepoRT con su commit, publica la partición en RAW, dbt construye Bronze–Silver–Gold con 46 pruebas y Spark valida claves antes de escribir la OBT." |
| 1:35–2:35 | 3. Predicción válida e inválida | `/docs` → `GET /modelo` (v5) → `POST /predecir` → Try it out con el ejemplo → 200: decisión, tiempos, `version_modelo`, `run_id`. Luego borrar `tipo_columna` → 422 con el campo | "La respuesta trae la acción y la versión que la produjo. Si falta un campo, 422 indica exactamente cuál." |
| 2:35–4:05 | 4. Reentrenamiento con pausa | Kestra → la ejecución de `reentrenamiento` en **PAUSED** → Logs de `comparar` (RMSE champion vs challenger y lo que recomienda la regla) → **Resume**: `aprobar = true`, motivo → `decidir` termina → MLflow: alias **champion en v6** → `/docs` `GET /modelo` muestra v6 (esperar ~30 s o `POST /admin/recargar` con el token) | "El flujo se detiene hasta que una persona decide. Al aprobar, el alias se mueve y la API toma el modelo nuevo sin reconstruir la imagen." |
| 4:05–4:55 | 5. Rollback | MLflow → Version 5 → Aliases → agregar `champion` (se mueve desde el v6) → `/docs` `GET /modelo` vuelve a v5 | "Volver atrás es mover el alias: menos de un minuto, sin tocar Docker." |
| 4:55–6:00 | 6. El lote con deriva dispara la alerta | Kestra → `monitoreo` → Execute `semana = 8` (~40 s) → Logs: `[ALERTA ALTA] … desempeno_rmse` y `desempeno_sesgo · deriva conceptual`. Luego el tablero → pestaña **Desempeño y negocio**: círculos rojos desde el lote 6 y líneas de reentrenamiento | "Desde el lote 6 simulamos un HPLC con 1 mL más de volumen de retardo. Los lotes sin alterar no alertan; los alterados sí." |
| 6:00–6:45 | 7. Interruptor de respaldo | `/docs` → `POST /admin/respaldo` sin token → 403. Con `x-admin-token` y `activo = true` → `POST /predecir`: `respaldo_usado: true`. Luego `activo = false` | "Con un interruptor protegido la API pasa a la regla de negocio; también existe la variable `USAR_RESPALDO`." |
| 6:45–7:00 | Cierre | Diapositiva o tablero | "El sistema detecta, alerta y se actualiza con aprobación humana; hoy no ahorra corridas y recomendamos ajustarlo con un piloto." |

## Si algo sale distinto

- **La regla no recomienda promover el v6:** igual se puede aprobar, explicando que la decisión final es humana, o rechazarlo y mostrar que el champion queda intacto. En ese caso, el cambio de modelo se demuestra con el rollback (alias a v2 y de vuelta a v5).
- **La ingesta tarda:** no esperar en cámara; mostrar la ejecución terminada.
- **`/modelo` no cambia de inmediato:** el TTL es de 30 s; usar `POST /admin/recargar` con el token.

## Después de grabar

Subir el video (YouTube no listado o Drive con acceso por enlace) y avisar para:
`python -m scripts.exportar_evidencia` (incluye el ciclo del video) y
`python -m scripts.construir_memo --video <URL>`.
