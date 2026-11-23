# Registro de cambios respecto a los PSets 1–3

Cada fila corresponde a una observación del profesor o a una decisión que cambió.
**Estado:** ✅ hecho y verificado · 🟡 parcial · ⏳ pendiente.
Las rutas son relativas a `proyecto_final/`.

## PSet 1 — Formulación y pitch (72/100)

| # | Observación | Cambio | Archivo(s) | Estado |
|---|---|---|---|---|
| 1.1 | Comparación y selección: justificar cada calificación de la matriz, incluir totales, explicar por qué la Idea 3 tiene mayor valor sin laboratorio ni costos operativos, y considerar la acción que habilita. | Matriz con la justificación de cada celda y los totales; criterio explícito de "acción habilitada" y declaración de que el valor de la Idea 3 es potencial (sin laboratorio ni costos medidos). | `docs/PSet4_memo_*.pdf` §1 | ⏳ |
| 1.2 | El umbral de coelución de 0.5 min coincide con el RMSE esperado: las alertas se confunden con el error del modelo. | En el PSet 3 el umbral fijo se reemplazó por un intervalo de predicción del 95 % para la diferencia entre dos compuestos, calibrado con predicciones fuera de pliegue. Se evaluará de nuevo con el modelo reentrenado. | `src/business_metrics.py`; memo §1 | 🟡 |
| 1.3 | Sustentar la reducción del 30 % de corridas y establecer una línea base de consumo de solventes. | El 30 % pasa a ser una hipótesis que no se reporta como ahorro. La línea base se define como (volumen de solvente por corrida × corridas preliminares por método); sus datos no existen en RepoRT y se piden al patrocinador (ver 1.4 y 1.8). El resultado de negocio se calcula con la métrica proxy de la simulación (PSet 4 §9). | memo §1 y §9; presentación | ⏳ |
| 1.4 | Viabilidad técnica: cómo obtener datos de consumo de solventes y de corridas por método; RepoRT y RDKit no bastan. | Fuente propuesta: bitácoras del cromatógrafo (corridas por método) y registros de compra o inventario de solventes del laboratorio piloto. Queda como requisito del piloto, no como dato disponible. | memo §1 y §10 | ⏳ |
| 1.5 | Viabilidad de negocio: qué laboratorio usaría la herramienta, quién decide y cómo se mide el ahorro frente al proceso actual. | Usuario, responsable de la decisión y protocolo de medición antes/después (mismo criterio de aceptación cromatográfica). | memo §1 y §8.5; presentación | ⏳ |
| 1.6 | Riesgos: un modelo entrenado con RepoRT puede no funcionar con columnas, equipos y condiciones de otro laboratorio; definir cómo comprobar la generalización. | Análisis de desempeño por subgrupo de tipo de columna (PSet 4 §8.1) como evidencia interna, criterio de retirada ligado a ese desempeño y, para el piloto, validación con corridas locales de control. | memo §8 y §10 | ⏳ |
| 1.7 | Alcance del semestre: incorporar un entregable de monitoreo al MVP con indicadores concretos. | El PSet 4 implementa el monitoreo (tabla MONITOREO, PSI, KS/chi², métricas por lote, alertas y tablero). | `monitoreo/`, `kestra/monitoreo.yml` | ⏳ |
| 1.8 | Pitch: sustentar el 30 %, incorporar la verificación y la severidad de los riesgos, y pedir recursos concretos (acceso a un laboratorio y registros de consumo). | La presentación del PSet 4 reemplaza las cifras del pitch por las de la sección 9 y cierra con una solicitud concreta de recursos. | `docs/PSet4_presentacion_*.pdf` | ⏳ |

## PSet 2 — Pipeline de datos (66/100)

| # | Observación | Cambio | Archivo(s) | Estado |
|---|---|---|---|---|
| 2.1 | Kestra: agregar un bloque de errores. | Bloque `errors` que registra la tarea y el snapshot fallidos y limpia la tabla transient y el stage. Verificado con un fallo real. | `kestra/ingesta.yml` | ✅ |
| 2.2 | Implementar un backfill histórico; reemplazar el snapshot no equivale a recuperar períodos. | RAW se particiona por `SNAPSHOT_DATE` con el commit de RepoRT (`SOURCE_COMMIT`); flow de backfill por rango de fechas. Cargados 2025-01-01, 2025-04-01 y el actual. | `kestra/ingesta.yml`, `kestra/backfill.yml`, `kestra/scripts/ingest_repo_rt.py` | ✅ |
| 2.3 | Automatizar dbt y Spark desde Kestra. | Las tareas `dbt_build` (DbtCLI) y `spark_obt` corren en contenedores dentro del mismo flow. | `kestra/ingesta.yml` | ✅ |
| 2.4 | Calidad: ampliar el diagnóstico a compuestos repetidos, retenciones extremas y unidades de flujo, y convertirlo en decisiones de limpieza. | Reglas aplicadas en Silver con su motivo por fila: rt ≤ t0, réplicas (mediana si el rango es ≤ 0.5 min, exclusión si es mayor), tope de 120 min y normalización de flujo a mL/min. Se excluye el 4.9 %. | `dbt/models/silver/int_registros_clasificados.sql`, `dbt/dbt_project.yml` | ✅ |
| 2.5 | dbt: Silver debe aplicar las reglas; agregar pruebas de dominio (rangos de retención, conservación de filas). | Test genérico `en_rango`, tests de conservación Raw → Bronze → Silver → Gold, RT > t0 y tope de exclusiones. 44/44 PASS. | `dbt/models/schema.yml`, `dbt/tests/` | ✅ |
| 2.6 | Star schema: eliminar `factor_retencion` si todos sus valores son nulos. | Columna eliminada de Bronze, Silver, Gold y OBT. | `dbt/models/` | ✅ |
| 2.7 | Spark: validar la unicidad de las dimensiones antes de los joins (no ocultar duplicados con una fila por clave) y detener el job antes de escribir. | Validación de claves, huérfanos y grano; `exit 1` sin escribir. Probado con un caso negativo. | `spark/obt_processing.py` | ✅ |
| 2.8 | Infraestructura: integrar dbt en Docker y automatizar la importación del flujo y sus scripts. | Imagen `qsrr-dbt`; el servicio `kestra-deploy` valida e importa los flows y los archivos de namespace en cada arranque. | `docker-compose.yml`, `dbt/Dockerfile`, `kestra/deploy.sh` | ✅ |

## PSet 3 — Experimentación (pendiente de calificación)

| # | Observación | Cambio | Archivo(s) | Estado |
|---|---|---|---|---|
| — | Pendiente de recibir comentarios. | — | — | ⏳ |

## Decisiones actualizadas

| Decisión | Antes | Ahora | Motivo | Estado |
|---|---|---|---|---|
| Grano de la OBT | Una medición por `(experiment_id, id)`. | Una observación por `(experimento, compuesto)`; las réplicas consistentes se colapsan en la mediana. | Observación 2.4: los compuestos repetidos sobrerrepresentaban réplicas. | ✅ |
| Datos de modelado C18 | 152 586 filas, 96 482 compuestos (SHA `0c366b46…`, PSet 3). | 137 539 filas, 95 625 compuestos y 219 experimentos de la OBT corregida (SHA `8b656cd0…`, commit RepoRT `420b550…`, snapshot 2026-11-20). | Consecuencia del nuevo grano y de las reglas de limpieza. | ✅ |
| Linaje en Gold y OBT | El hecho y la OBT no guardaban de qué snapshot venían. | `SNAPSHOT_DATE` y `SOURCE_COMMIT` en `FACT_RETENCION_CROMATOGRAFICA` y `OBT_QSRR_FINAL` (2 pruebas dbt nuevas, 46/46 PASS); se registran como tags de cada corrida de MLflow. | PSet 4 §10.6: una predicción debe rastrearse hasta el snapshot de la OBT y las tablas Gold. | ✅ |
| Esquema de partición | Holdout aleatorio agrupado por compuesto (80/20). | Partición temporal por orden de llegada a RepoRT (`EXPERIMENTO_ID`, la OBT no tiene fechas): entrenamiento = experimentos 0006–0275 (75 % de filas, 103 200); producción simulada = 10 lotes consecutivos 0276–0437. Ningún experimento se parte. La CV sigue agrupada por compuesto dentro del entrenamiento. 0,80+ dejaba lotes de < 250 filas. | PSet 4 §5: simular producción con datos posteriores al corte. El experimento 0186 (SMRT) concentra el 58 % de las filas. | ✅ `src/splits.py`, `docs/lotes.csv` |
| Champion | HGB v5 del Codespace, run `04483473…`, RMSE CV 2,592 ± 0,250. | HGB **v1** del registro local, run `f6617bca…`, mismos hiperparámetros del PSet 3 sin repetir el tuning; RMSE CV **2,489 ± 0,054**; intervalo de coelución calibrado −9,47 / +9,76 min. | El modelo anterior se entrenó con la OBT sin corregir y otro split. | ✅ `scripts/registrar_champion.py` |
| Restricciones de monotonía | — | Evaluadas y **no adoptadas**: corregir el flujo (−1) sube el RMSE de los lotes nuevos de 3,05 a 3,75 min (+23 %) y no corrige las series homólogas. El defecto queda documentado como `xfail(strict=True)` y como criterio de promoción. | Las pruebas de comportamiento (PSet 4 §3.3) detectaron que el flujo actúa como proxy del método porque falta el programa de gradiente. | ✅ `tests/test_comportamiento.py`, `src/reentrenar.py` |
| Umbral de decisión | Intervalo del 95 % de la diferencia entre pares (PSet 3). | Se mantiene. En la simulación con métodos de 5 analitos aprueba 0 % de los métodos (RMSE en lotes 3,05 min); empieza a ahorrar corridas solo con RMSE ≤ ≈0,5 min, y el techo de ahorro es 19 % (métodos realmente separables). Umbrales más laxos (0,5 o 1 min) aprueban más, pero con precisión de 36–40 % frente a una tasa base de 26 %: pierden más corridas de las que ahorran. | PSet 4 §9 y observación 1.3: reemplazar el 30 % hipotético por cifras medidas. | ✅ |
| Salida secundaria | — | La API devuelve el orden de elución predicho y marca como confiable cada par adyacente con diferencia predicha ≥ 2 min (91–96 % de acierto en lotes nuevos). No cambia la decisión. | Valor útil hoy mientras el error no permite aprobar métodos. | ✅ `api/main.py`, `src/business_metrics.py` |
| Patrón de despliegue | Streamlit con predicción (PSet 1). | API online (FastAPI) bajo demanda; la simulación de lotes la llama desde Kestra. | Horizonte "inmediato, antes de inyectar" del PSet 1. | ✅ |
| Campo `factor_retencion` | Columna nula en Gold y OBT. | Eliminado. | Observación 2.6. | ✅ |
| Snapshot de origen | Un único snapshot que se reemplaza en cada carga. | Particiones por fecha con su commit de RepoRT; Gold usa la más reciente. | Observación 2.2 y trazabilidad (PSet 4 §10.6). | ✅ |
| Lectura de SMILES | Desde todas las filas de RAW. | Solo desde el snapshot más reciente, el mismo del que se construyó Gold. | RAW ahora guarda varios snapshots. | ✅ |
| Estructura del repositorio | `psets/pset-02` y `psets/pset-03` por separado. | Todo en `proyecto_final/`, con un solo `docker-compose.yml`. Las carpetas `psets/` quedan como historial (etiqueta `pset3-entrega`). | PSet 4 §10.1–10.2. | ✅ |
