# Simulación de producción, monitoreo y reentrenamiento (PSet 4 §5–7)

Evidencia ejecutable: `notebooks/06_simulacion_produccion.ipynb` y
`notebooks/07_analisis_monitoreo.ipynb`. Datos: `docs/predicciones.csv`,
`docs/monitoreo.csv`, `docs/alertas.csv`, `docs/reentrenamientos.csv` y
`docs/rollback.csv`.

## Lotes

La OBT no tiene fechas. El orden de llegada se aproxima con `EXPERIMENTO_ID` de
RepoRT, que crece a medida que los laboratorios depositan datos. El
entrenamiento usa los experimentos 0006–0275 (103 200 filas). La producción
simulada son 10 lotes consecutivos, 0276–0437 (34 339 filas), cortados en
bloques de unas 3 500 filas sin partir ningún experimento (`src/splits.py`,
`docs/lotes.csv`). El lote *k* es la semana *k* a partir del 05-01-2026.

**Horizonte.** El tiempo medido de un método llega cuando se inyecta, una
semana después de la predicción. En la semana *k*, Kestra predice el lote *k*
y publica en `TARGETS` las mediciones del lote *k-1*, que hasta entonces
estaban ocultas en `LAB_MEDICIONES`. Por eso hay 11 semanas para 10 lotes.

**Limitaciones.** El ID ordena depósitos, no inyecciones. Los lotes 06, 09 y 10
tienen un solo experimento, así que la variación entre lotes mezcla deriva con
cambio de laboratorio. Por eso los umbrales se calibran con pseudo-lotes del
entrenamiento.

## Deriva inducida (qué se alteró exactamente)

Desde el lote 06, `TIEMPO_RETENCION` se reemplaza por
`TIEMPO_RETENCION + 1,0 / F`, donde F es el flujo del método en mL/min.
Representa una transferencia de los métodos de un UHPLC (volumen de retardo de
unos 0,1 mL) a un HPLC convencional (unos 1,1 mL): el gradiente llega 1,0/F min
más tarde. El valor original queda en `TIEMPO_RETENCION_ORIGINAL`. Los lotes 09
y 10 no reportan flujo, así que se asume F = 0,4 mL/min.

**Las entradas no cambian, así que es deriva conceptual.** Retraso medio por
lote: 06 = 1,67 min · 07 = 3,23 min (máximo 25 min, con un método a
0,04 mL/min) · 08 = 3,57 · 09 = 2,50 · 10 = 2,50.

Con 0,5 mL, el sesgo del lote 06 (-1,05 min) quedaba dentro del umbral
calibrado (1,81 min) y no se distinguía de la degradación natural.

## Resultado del monitoreo

| Lote evaluado | RMSE (min) | Sesgo (min) | Diagnóstico | Alertas |
|---|---|---|---|---|
| 1–4 | 0,74–1,96 | -0,20 a +0,96 | estable | solo calidad de datos (ver abajo) |
| 5 | 1,43 | -0,20 | deriva de datos sin impacto | PSI en 2 descriptores |
| 6 | 2,18 | **-1,88** | deriva conceptual | sesgo |
| 7 | **5,34** | **-3,20** | deriva conceptual | RMSE, sesgo → **reentrenamiento (semana 8)** |
| 8 | **5,07** | -1,20 | deriva conceptual + degradación natural | RMSE |
| 9 | 3,43 | **-2,77** | deriva conceptual | sesgo → **reentrenamiento (semana 10)** |
| 10 | **8,28** | **+5,67** | deriva de datos con impacto (100 % fuera de dominio) | RMSE, sesgo, PSI, dominio |

Sin la deriva inducida, los lotes 06, 07 y 09 quedan dentro de los umbrales.
Los lotes 08 y 10 fallan igual, por métodos fuera del dominio de entrenamiento.

## Falsas alarmas en lotes sin alterar

| Semana | Alerta | Causa | Ajuste |
|---|---|---|---|
| 1 | `errores_4xx` (14,5 %) | 12 solicitudes con `b_meoh = 'NA'` en RepoRT; la API las rechaza con 422, como debe. | Alarma real de calidad: limpiar `'NA'` en Silver. Se mantiene el umbral. |
| 1–4 | `categoria_no_vista` | Cada laboratorio nuevo trae su propia columna o fase. El modelo usa descriptores numéricos, así que no le afecta. | Ya es severidad baja: dejarla informativa o cruzarla con el desempeño. |
| 5 | `deriva_datos` | 2 descriptores (mol_tpsa, mol_h_donors) apenas sobre p99, con buen desempeño. | Exigir 3 descriptores: el lote 05 deja de alertar y el lote 10 (4) sigue alertando. |

Ninguna alerta de desempeño ni de reentrenamiento cayó en un lote sin alterar.
Con el umbral clásico (PSI > 0,25), los 5 lotes sin alterar habrían alertado.

## Ciclos de reentrenamiento

| Semana | Disparo | Challenger | Lote de evaluación | RMSE champion → challenger | Regla | Decisión |
|---|---|---|---|---|---|---|
| 8 | Desempeño en los lotes 6 y 7 | v4 | 7 | 5,34 → 5,31 | no promueve (0,03 < 1 DE de CV) | rechazado |
| 10 | Desempeño en los lotes 8 y 9 | v5 | 9 | 3,43 → 2,86 | promueve | **aprobado**: champion = v5 |

**Lección.** Evaluado fuera de línea, el v4 rechazado habría mejorado al v2 en
los lotes 08–10 (4,85 / 2,46 / 7,03 frente a 5,07 / 3,43 / 8,28). La regla
decidió con un solo lote, el peor de la deriva. Ajuste propuesto: evaluar sobre
los 2 lotes etiquetados más recientes y comparar la mejora con la variación
entre lotes, no con la de la CV.

**Rollback.** Se movió el alias `champion` de v5 a v2 y de vuelta a v5. La API
siguió cada cambio en unos 35 s (TTL de 30 s), sin reconstruir ni reiniciar el
contenedor (`docs/rollback.csv`).
