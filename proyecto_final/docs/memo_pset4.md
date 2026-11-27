% QSRR-Predict · Documento técnico del proyecto final (PSet 4)
% Jonatan Buenaño Peñafiel · Ciencia de Datos · USFQ · noviembre de 2026
% Repositorio: proyecto_final/ (rama pset4) · Video de la demostración: {{VIDEO}}

# 1. Problema y formulación

Desarrollar un método por HPLC exige corridas exploratorias de prueba y error para comprobar que los picos de una mezcla se separan. QSRR-Predict predice el tiempo de retención de cada analito a partir de su estructura (SMILES) y del método (columna, fase móvil, flujo, gradiente, pH y dimensiones de la columna). Con esa predicción decide si las condiciones pueden aprobarse sin la corrida exploratoria o si el analista debe revisarlas. La tabla resume la formulación final, ya con las decisiones que cambiaron durante el proyecto (detalle en el anexo C, `docs/cambios.md`).

| Elemento | Decisión final | Cambio respecto al PSet 1 |
|---|---|---|
| Unidad | Un analito dentro de un método cromatográfico (experimento × compuesto). Una solicitud es un método con varios analitos. | Antes "compuesto bajo condiciones"; ahora el método trae su gradiente y su columna. |
| Target | Tiempo de retención medido (min) en columnas C18 de RepoRT. | Sin cambio. |
| Horizonte | Inmediato: la predicción se necesita al diseñar el método, antes de preparar reactivos. El tiempo real llega cuando se inyecta (en la simulación, una semana después). | Se explicitó cuándo llega el target. |
| Métrica técnica | RMSE (min), con el MAE como complemento. | Se retiró el R² como criterio: no se traduce en una decisión. |
| Métrica de negocio | Corridas exploratorias evitadas netas por método: aprobaciones correctas menos aprobaciones que fallan (cada fallo obliga a repetir). | Reemplaza el "30 % de ahorro", que era una hipótesis (obs. 1.3). |
| Línea base | De negocio: el proceso actual (revisar siempre), que ahorra 0. Técnica: la mediana del tiempo por condición (columna, fase y flujo). | Ridge pasó a ser un candidato más. |
| Umbral de decisión | Se aprueba un método solo si ningún par de picos adyacentes predichos tiene un intervalo del 95 % de su diferencia que incluya el 0. El intervalo se calibra con pares fuera de pliegue. | Reemplaza el umbral fijo de 0,5 min, que coincidía con el error del modelo (obs. 1.2). |
| Juicio humano | El analista decide si inyecta. Una persona aprueba cada cambio de modelo en producción. | Se agregó la aprobación de modelos (sección 6). |

**Por qué este caso y no los otros dos del PSet 1 (obs. 1.1).** En la matriz del PSet 1, la Idea 3 sumó 18 de 18 puntos, frente a 13 (inventarios) y 12 (blísteres). La razón principal es el acceso a datos: RepoRT es público y las otras dos ideas dependían de un ERP o de cámaras de planta inaccesibles. La segunda razón es la **acción habilitada**: aprobar o revisar un método antes de inyectar es una decisión directa y verificable con la siguiente corrida. Hay que reconocer un límite: sin un laboratorio ni costos medidos, el valor de la Idea 3 es potencial. Por eso la métrica de negocio se mide con un proxy en la simulación (sección 9) y no se reporta un ahorro en dinero.

**Quién la usaría y cómo se mediría el ahorro (obs. 1.4 y 1.5).** La usaría el analista de desarrollo analítico de un laboratorio de control de calidad farmacéutico, y el jefe de laboratorio decide adoptarla. El ahorro real se mide en un piloto antes y después: corridas exploratorias por método aceptado y mL de solvente por método, tomados de la bitácora del cromatógrafo y del inventario de solventes, con el mismo criterio de aceptación de separación en ambos periodos. Esos datos no existen en RepoRT y son lo que se pide al patrocinador.

# 2. Arquitectura end-to-end

![Arquitectura del proyecto: datos (PSet 2), modelo (PSet 3) y operación (PSet 4).](docs/arquitectura.png){width=100}

**Cómo fluye.** Kestra descarga RepoRT cada semana y publica una partición por fecha en `RAW`, con el commit de origen. dbt construye Bronze, Silver y Gold, y Spark valida las claves y escribe la OBT. Desde la OBT se entrenó y registró el modelo en MLflow. La API carga siempre `models:/qsrr-predict-modelo@champion`, así que la imagen de Docker no contiene el modelo. En la simulación, Kestra envía cada lote a la API, guarda predicciones y targets en el esquema `PRODUCCION` de Snowflake y lanza el monitoreo. El monitoreo dispara el reentrenamiento, que se detiene hasta que una persona aprueba. Todo se levanta con `docker compose up -d --build`: Kestra, Spark, MLflow, la API y el tablero.

# 3. Datos

## Ingesta, reintentos y backfill

El flow `ingesta` resuelve la fecha lógica al último commit de RepoRT de ese día, así que cada carga queda ligada a un SHA inmutable. Reemplaza solo la partición `SNAPSHOT_DATE` en una transacción, lo que hace la carga idempotente. Cada paso de red o de Snowflake reintenta hasta 3 veces. Un bloque `errors` registra la tarea fallida y limpia el stage y la tabla transient, de modo que un fallo nunca deja RAW a medias. El flow `backfill` recorre un rango de fechas y reconstruye lo que RepoRT publicaba en cada periodo; se probó con 2025-01-01, 2025-04-01 y el snapshot actual. En el PSet 4 la ingesta suma el pH de las fases A y B y el programa de gradiente (`_gradient.tsv`), con un `ALTER TABLE … ADD COLUMN IF NOT EXISTS` que mantiene compatible el backfill.

## Calidad: problema, métrica y decisión

| Problema | Evidencia medida | Decisión en Silver |
|---|---|---|
| Retención ≤ t0 | 3 912 filas en 151 experimentos | Excluir: el analito no fue retenido. |
| t0 = 0 | 14 389 filas | Tratar como nulo, porque RepoRT usa 0 para "no reportado". |
| Réplicas del mismo compuesto | 8 279 pares; rango mediano 0,06 min | Si el rango es ≤ 0,5 min, mediana; si es mayor, excluir por inconsistente. |
| Retenciones extremas | p99 = 21,9 min; máximo = 100,5 min | Se conservan (gradientes largos), con un tope físico de 120 min. |
| Longitud de columna de 5 mm | La prueba `en_rango` falló en el exp. 0008 | El t0 es coherente con ese volumen, así que es un dato real: el rango se amplió a 1–500 mm. |

Cada fila excluida conserva su motivo en `SILVER.INT_REGISTROS_CLASIFICADOS`. La calidad se verifica con 46 pruebas de dbt: dominio, conservación de filas entre capas y relaciones.

## Bronze, Silver, Gold y OBT

![Modelo dimensional de la capa Gold.](docs/modelo_dimensional.png){width=78}

Bronze estandariza nombres y tipos sin descartar filas. Silver clasifica y deduplica. Gold es un esquema estrella:

- **Tabla de hechos:** `FACT_RETENCION_CROMATOGRAFICA`, con grano **experimento × compuesto**. Guarda la mediana de las réplicas, el `SNAPSHOT_DATE` y el `SOURCE_COMMIT`.
- **Dimensiones:** `DIM_COMPUESTO` (por InChIKey), `DIM_CONDICIONES` (columna × fase × flujo) y `DIM_METODO` (por experimento, nueva en el PSet 4).

Spark valida que las claves sean únicas y no nulas y que no haya hechos huérfanos **antes** del join. Después comprueba que la OBT tenga exactamente las filas del hecho; si algo falla, termina sin escribir. La OBT C18 actual tiene 137 539 filas, 95 625 compuestos y 219 experimentos (SHA `8b656cd0…`).

## Batch frente a streaming

RepoRT es un repositorio que se actualiza, no una fuente de eventos, así que una ingesta semanal por lotes basta. Además, permite reconstruir cualquier snapshot con su SHA. Habría streaming si los cromatógrafos de un laboratorio publicaran sus corridas en tiempo real para recalibrar el modelo, lo que exigiría carga incremental, checkpoints y manejo de eventos tardíos.

# 4. Modelado

**Hallazgos de la EDA que cambiaron el experimento.**

- **Distribución.** La retención es bimodal (2–6 y 10–16 min) y sin cola larga. Por eso se mantuvo el RMSE; con log(1+y) empeoraba.
- **Compuestos repetidos.** El mismo compuesto aparece en muchos métodos, así que la CV agrupa por InChIKey.
- **Flujo como proxy.** El flujo era la variable más asociada al tiempo (Spearman −0,72), pero las pruebas de comportamiento del PSet 4 mostraron que actuaba como sustituto del método, porque faltaba el gradiente. Por eso se ingirieron los descriptores del método.
- **Fecha de corte.** La OBT no tiene fechas, así que el `EXPERIMENTO_ID` de RepoRT se usa como orden de llegada:
  - experimentos 0006–0275: entrenamiento (103 200 filas);
  - experimentos 0276–0437: 10 lotes de producción simulada.

**Features y prueba de no fuga.** Son 28 features, todas conocidas antes de inyectar:

- 9 descriptores RDKit;
- 6 fracciones de solvente de las fases A y B;
- el flujo;
- t0, longitud, diámetro, partícula y volumen de la columna;
- el pH de A y de B;
- 5 descriptores del gradiente: % orgánico inicial y máximo, tiempo al máximo, pendiente y duración.

`model_inputs` separa X, y y los grupos, y la imputación vive dentro del `Pipeline`. El notebook 02 verifica con `assert` que no entren el target ni los IDs, que los grupos sean disjuntos por pliegue y que el preprocesamiento se ajuste solo con el pliegue de entrenamiento.

**Validación.** El esquema combina dos niveles:

- un corte temporal por experimento, que separa el entrenamiento de la producción;
- dentro del entrenamiento, `GroupKFold(5)` por compuesto.

La regla de promoción y el monitoreo usan la desviación estándar de esa CV. Los lotes de producción hacen de conjunto reservado: solo se usan para comparar champion y challenger, no para elegir entre candidatos ni para el benchmark con Gemini, que no se repitió (obs. 3.1).

| Modelo (PSet 3, CV agrupada) | RMSE CV (min) | Comentario |
|---|---|---|
| Mediana global | 5,83 ± 0,09 | Línea base trivial |
| Mediana por condición | 3,77 ± 0,41 | Línea base técnica |
| Ridge / KNN / MLP | 3,18 / 3,06 / 2,76 | Candidatos |
| Random Forest (tuning) | 2,57 ± 0,21 | Challenger del PSet 3 |
| **HistGradientBoosting (tuning)** | **2,59 ± 0,25** | Champion: igual al RF en CV, pero mejor en holdout, 0,7 MB frente a 159 MB |

**Tuning.** Búsqueda aleatoria de 30 configuraciones por familia con el mismo GroupKFold. La mejora frente a la configuración por defecto (0,01–0,11 min) quedó por debajo de la variación entre pliegues, así que no fue concluyente. En el PSet 4 **no se repitió el tuning**: se reentrenó con los hiperparámetros del champion del PSet 3 (learning_rate 0,18; 200 iteraciones; 31 hojas; L2 4,94). Las 90 corridas hijas del tuning no guardan el modelo, solo los parámetros, la semilla, el SHA de los datos y el commit (obs. 3.2). Con eso basta para reconstruirlas: `scripts/reproducir_corrida.py` reentrena la v2 desde MLflow y la reproduce con predicciones idénticas (diferencia máxima 0 min).

**Modelo ganador.**

- **v1** (run `f6617bca…`): OBT corregida y split por experimento, 16 features, RMSE CV 2,489 ± 0,054.
- **v2** (run `ac566f02…`): agrega los descriptores del método (28 features), RMSE CV 2,343 ± 0,035. Fue el champion de la simulación.
- **v5** (run `372817b3…`, CV 2,245 ± 0,031): el challenger aprobado en el reentrenamiento. **Es el champion actual.**

# 5. Despliegue

**Patrón: online.**

- **Latencia.** La decisión se toma mientras el analista diseña un método, así que la predicción se necesita en segundos.
- **Frecuencia y volumen.** Los datos llegan a demanda, cuando se diseña un método. En la simulación hubo entre 27 y 131 solicitudes por semana, con 1 300 a 6 500 analitos.
- **Por qué no batch.** La combinación de métodos y compuestos no se puede precalcular: cada método nuevo es una combinación nueva.
- **Costo de una predicción desactualizada.** Es bajo, porque el modelo cambia como mucho una vez por ciclo de reentrenamiento; el costo real está en no tener la predicción a tiempo.
- **Cuándo convendría batch.** Si el laboratorio trabajara con un catálogo fijo de métodos y una lista conocida de analitos que se planifica en una reunión semanal, bastaría una tabla de predicciones recalculada cada noche y guardada en Snowflake.

**Servicio.** FastAPI en Docker con `/salud`, `/modelo`, `/predecir` y `/metricas`, además de `/admin/respaldo` y `/admin/recargar`, protegidos con un token. El esquema de Pydantic replica la firma de MLflow (tipos, rangos y categorías) y devuelve un 422 que nombra el campo que falló. Cada predicción se registra con su id, timestamp, entradas, salida, versión, run_id y latencia, y Kestra la carga en `PRODUCCION.PREDICCIONES`. Una guardia de dominio marca `fuera_de_dominio` y fuerza "revisar" cuando algún descriptor del método queda fuera del rango de entrenamiento.

| Solicitud (resumen) | Respuesta (resumen) |
|---|---|
| `POST /predecir` con columna Waters ACQUITY BEH C18, ACN, 0,4 mL/min, gradiente 5→95 % en 10 min, cafeína e ibuprofeno | `decision: revisar_condiciones` · cafeína 3,72 min, ibuprofeno 7,27 min · 1 par en riesgo · orden de elución confiable · `version_modelo: 5`, `run_id: 372817b3…` · 68 ms |
| La misma solicitud sin `tipo_columna` y con `fase_movil: "agua y alcohol"` | HTTP 422: `tipo_columna: Field required; fase_movil: formato esperado 'A[H2O=x; …] B[…]'` |

**Qué cubren las pruebas (56).**

- **Contrato:** 200 con el esquema, y 422 por campo faltante, tipo incorrecto o categoría desconocida.
- **Modelo:** reproduce el RMSE y el MAE registrados en una muestra fija de 400 filas guardada en el repositorio, con tolerancia de 10⁻³ min. El modelo es determinista; la tolerancia solo cubre diferencias de punto flotante entre sistemas.
- **Comportamiento:** las moléculas lipofílicas retienen más que las polares.
  - Dos pruebas de física son `xfail(strict=True)`, como defectos documentados: más flujo no debería aumentar la retención, y un homólogo más largo no debería eluir antes.
- **Respaldo:** si el modelo no carga, responde con la línea base y lo indica.
- **Interruptor:** se activa y se desactiva, y exige token.
- **Simulación y monitoreo:** lotes, horizonte, deriva inducida y PSI.

**Qué queda fuera de CI.** En CI no hay MLflow ni Snowflake: se usa la copia del modelo de `tests/fixtures/`. Por eso quedan fuera los flujos de Kestra, la carga a Snowflake y el monitoreo con datos reales; se validan con la simulación (sección 7). `ci.yml` instala dependencias, construye la imagen y ejecuta pytest en cada push y pull request. `cd.yml` publica la imagen en GHCR con el hash del commit en cada merge a `master` con CI en verde.

{{CAPTURA_CI}}

# 6. Versionado, reentrenamiento y despliegue continuo

**Regla de promoción.** Champion y challenger se evalúan en el **mismo lote etiquetado más reciente, que ninguno de los dos vio**. El challenger se promueve si:

- su RMSE es menor que el del champion por **más de una desviación estándar de la CV del champion** (0,035 min);
- y su métrica de negocio no es peor.

Aunque la regla lo recomiende, el cambio espera la aprobación de una persona.

**Disparador y ventana.**

- **Por desempeño:** RMSE o sesgo sobre su umbral en **2 lotes evaluados seguidos** con el champion vigente. Con 1 lote bastaría un laboratorio atípico; con 3, se predecirían tres semanas con un sesgo conocido.
- **Por calendario:** cada 8 lotes evaluados.
- **Qué no dispara:** la deriva de datos sin caída de desempeño. Solo se usan lotes cuyo target ya llegó.
- **Ventana:** todo el histórico (peso 1) más los lotes con target (peso 10). Lo reciente refleja el cambio del laboratorio, y las 103 200 filas históricas sostienen la química del modelo.
- **Registro:** cada corrida se registra en MLflow con `fase=reentrenamiento` y el motivo, y se convierte en una versión con el alias `challenger`.

| Semana | Motivo | Challenger | Lote evaluado | RMSE champion → challenger | Regla | Decisión humana |
|---|---|---|---|---|---|---|
| 8 | Alerta en los lotes 6 y 7 | v4 | 7 | 5,340 → 5,310 (−0,030) | No promueve | Rechazado: la mejora es menor que 1 DE |
| 10 | Alerta en los lotes 8 y 9 | v5 | 9 | 3,427 → 2,862 (−0,565) | Promueve | **Aprobado:** champion = v5 |

**Rollback.** Se movió el alias `champion` de v5 a v2 y luego de vuelta a v5. `/modelo` y las predicciones siguieron cada cambio en unos 35 s (TTL de 30 s), sin reconstruir ni reiniciar el contenedor (`docs/rollback.csv`, notebook 06).

| Paso | /modelo | Versión en la predicción | Cafeína (min) |
|---|---|---|---|
| Antes | v5 | v5 | 3,717 |
| Alias champion → v2 | v2 | v2 | 2,892 |
| Alias champion → v5 | v5 | v5 | 3,717 |

**Por qué el modelo no se promueve automáticamente.** El código se despliega solo, porque las pruebas definen su contrato. El modelo, en cambio, se evalúa en **un** lote de **pocos** laboratorios, y la simulación mostró que eso engaña: el v4 rechazado habría mejorado al v2 en los lotes 8–10 (4,85 / 2,46 / 7,03 frente a 5,07 / 3,43 / 8,28). Además, un sesgo de tiempo puede venir del equipo y no del modelo. Una persona decide con ese contexto. Se propone, sin aplicarla todavía, una regla que evalúe sobre 2 lotes y compare con la variación entre lotes.

# 7. Simulación, monitoreo y alertas

**Lotes.** Son 10 lotes consecutivos (experimentos 0276–0437, 34 339 filas), de unas 3 500 filas cada uno, sin partir ningún experimento. El lote *k* se predice en la semana *k* y su target llega en la semana *k+1*, así que hay 11 semanas. La notebook 06 verifica el horizonte: cada target llegó una semana después y siempre después de sus predicciones. **Límite:** el ID ordena depósitos, no inyecciones, y los lotes 06, 09 y 10 tienen un solo experimento.

**Qué se alteró.** Desde el lote 06, cada tiempo medido se reemplazó por `t + 1,0 / F`, donde F es el flujo en mL/min. Simula la transferencia del método de un UHPLC a un HPLC con 1,0 mL más de volumen de retardo. Las entradas no cambian, así que es **deriva conceptual**. El retraso medio por lote fue de 1,7 a 3,6 min. En los lotes 09 y 10 no hay flujo reportado, y se asumió F = 0,4 mL/min.

![Desempeño por lote evaluado: RMSE frente a la línea base y sesgo. Líneas grises: reentrenamientos; círculos: alertas.](docs/figuras/desempeno_por_lote.png){width=100}

**Umbrales.** Cada lote es la librería de otro laboratorio. Con el umbral clásico (PSI > 0,25) habrían alertado los 5 lotes sin alterar, y KS y chi-cuadrado rechazan (p < 0,01) en todos los lotes. Por eso:

- El umbral de PSI de cada descriptor es el percentil 99 de 200 *pseudo-lotes* de experimentos del entrenamiento, y la alerta exige 2 descriptores. KS confirma.
- Los umbrales de desempeño son el percentil 95 del RMSE (3,66 min) y del |sesgo| (1,81 min) fuera de pliegue de esos pseudo-lotes.
- La comparación con la CV que pide el enunciado se reporta (`z_vs_cv`), pero no decide: su desviación (0,035) mide la variación entre pliegues por compuesto, no entre laboratorios.

| Alerta | Umbral | Ventana | Severidad | Recibe | Acción |
|---|---|---|---|---|---|
| RMSE del lote | > 3,66 min | 1 lote | Alta | Ciencia de datos | Diagnosticar; con 2 lotes, reentrenar |
| Sesgo del lote | > 1,81 min | 1 lote | Alta | Ciencia de datos + laboratorio | Revisar equipo y método; con 2 lotes, reentrenar |
| Deriva de datos | ≥ 2 descriptores con PSI > p99 | 1 lote | Media | Equipo de datos | Revisar la fuente; no reentrenar |
| Fuera de dominio | > 20 % de analitos | 1 lote | Alta | Analistas + ciencia de datos | Corrida de confirmación; incluir esos métodos al reentrenar |
| Categoría no vista | > 50 % | 1 lote | Baja | Equipo de datos | Informativa |
| Latencia p95 · 4xx · 5xx | > 500 ms · > 5 % · > 1 % | 1 lote | Media · Media · Alta | Plataforma / datos | Escalar · revisar solicitudes · respaldo |

**Resultado.**

- **Lotes sin alterar (1–5):** ninguna alerta de desempeño, con RMSE de 0,74 a 1,96 min.
- **Lote 06:** dispara la alerta de sesgo en el primer lote alterado (−1,88 min).
- **Lote 07:** dispara RMSE y sesgo, y con eso el reentrenamiento.
- **Sin la deriva inducida:** los lotes 06, 07 y 09 quedan dentro de los umbrales.
- **Lotes 08 y 10:** fallan incluso sin la deriva, porque tienen métodos fuera de dominio (10,6 % y 100 %).

Las **falsas alarmas** en lotes sin alterar fueron de severidad media o baja:

- **4xx en la semana 1 (14,5 %):** 12 solicitudes con `b_meoh = 'NA'` en RepoRT, que la API rechaza como debe. Es una alarma real de calidad.
- **Categoría no vista (semanas 1–4):** cada laboratorio trae su propia columna.
- **Deriva de datos en el lote 05:** 2 descriptores apenas sobre el umbral, con buen RMSE. Exigir 3 descriptores la elimina y conserva la alerta del lote 10 (4 descriptores).

| Entradas | Desempeño | Diagnóstico | Acción en el proyecto | Dónde ocurrió |
|---|---|---|---|---|
| Cambian | Se mantiene | Deriva de datos sin impacto | Avisar al equipo de datos; no reentrenar | Lote 05 |
| Cambian | Cae | Deriva de datos con impacto | Forzar "revisar" fuera de dominio; reentrenar con esos métodos | Lote 10 |
| Estables | Cae | Deriva conceptual | Revisar el equipo con el laboratorio; reentrenar con peso en lo reciente | Lotes 06–09 |

El monitoreo de cada semana corre en `monitoreo.yml`, guarda las métricas en `PRODUCCION.MONITOREO` y las alertas en `ALERTAS` y en el log de Kestra. El tablero en Streamlit (puerto 8501) muestra lote por lote las métricas de sistema, modelo, desempeño y deriva, con las alertas y los reentrenamientos marcados (anexo B). Del lado de sistema, la latencia p95 nunca pasó de 55 ms y no hubo errores 5xx.

# 8. Ética y retirada

**Subgrupos.**

| Subgrupo (lotes 1–5, sin deriva) | RMSE (min) | Lectura |
|---|---|---|
| Acetonitrilo / metanol | 1,30 / 1,68 | El metanol tiene un 29 % más de error; con la deriva absorbe el sesgo (−3,2 min), porque sus métodos usan menos flujo. |
| Analitos polares / apolares (terciles de logP) | 1,44 / 1,60 | Error similar, pero los polares eluyen en la zona más congestionada. |
| Columnas Waters / Agilent (dentro de dominio, todos los lotes) | 1,68 / 5,58 | Agilent es el 78 % de las filas de entrenamiento, pero solo 8 experimentos (SMRT). Waters tiene 57. Lo que generaliza es la diversidad de métodos. |

Hoy la decisión es idéntica en todos los subgrupos (100 % "revisar"), así que nadie recibe un trato distinto. Para el negocio la diferencia es aceptable mientras se revise siempre. Para las personas afectadas no lo sería si se activara la aprobación con un umbral único: los métodos con metanol, los analitos polares y las columnas Agilent serían los primeros en recibir una aprobación equivocada. Si se activa la aprobación, el intervalo debe calibrarse por modificador y por fabricante.

**Costo del error.**

| Error | Quién lo asume |
|---|---|
| Falso "aprobar" (los picos coeluyen) | El analista (repite la corrida y gasta solvente y tiempo de equipo) y, si no se detecta, el área de calidad o el cliente que recibe un resultado mal resuelto. |
| Falso "revisar" | El laboratorio, como costo de oportunidad. Es el proceso actual. |
| Subestimar el tiempo | El analista: el pico sale fuera de la ventana y hay que alargar el método. |
| Sobrestimar el tiempo | El laboratorio: corridas más largas de lo necesario. |

**Criterios de retirada.**

| # | Condición observable | Umbral | Respuesta |
|---|---|---|---|
| R1 | El modelo no supera al proceso actual después de reentrenar | Corridas netas < 0 durante 2 lotes | Modo de respaldo y revisión del modelo |
| R2 | El error sigue alto con un champion recién promovido | RMSE > 3,66 min en 2 lotes | Respaldo; la predicción queda solo como referencia |
| R3 | Las aprobaciones fallan | > 2 % de aprobaciones fallidas en un lote | Forzar "revisar" para todo y recalibrar el intervalo |
| R4 | Métodos o fabricantes fuera de dominio | > 50 % fuera de dominio en 2 lotes, o RMSE de un fabricante > 3,66 | Reentrenar con esos métodos; respaldo para ese subgrupo |
| R5 | Servicio degradado | 5xx > 1 % o p95 > 500 ms | Respaldo automático; plataforma corrige |

**Interruptor de respaldo.** Funciona por dos vías:

- la variable `USAR_RESPALDO=true`, que se aplica al reiniciar el contenedor, sin reconstruir la imagen;
- el endpoint `POST /admin/respaldo` con el header `X-Admin-Token`.

Se demostró en la notebook 07: sin token responde 403; con el interruptor activado, `respaldo_usado: true` y la predicción es la mediana por condición; al desactivarlo, vuelve el v5.

**Supervisión humana.** El juicio humano del PSet 1 se mantiene y se amplía en dos puntos:

- una persona aprueba cada cambio de modelo;
- ante una alerta de sesgo, el laboratorio confirma primero si cambió el equipo, porque un sesgo instrumental se corrige en el método y no con más datos.

Mientras el modelo no apruebe métodos, el analista usa el **orden de elución** predicho para planificar la corrida exploratoria.

# 9. Resultado de negocio

![Corridas exploratorias evitadas netas por método y lote: el modelo, el proceso actual y aprobar todo sin revisar. Líneas punteadas: reentrenamientos.](docs/figuras/negocio_por_lote.png){width=92}

| Lote | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Modelo (corridas netas por método) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Proceso actual / no hacer nada | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Aprobar todo sin revisar | −0,57 | −0,70 | −0,76 | −0,30 | −0,80 | −0,87 | −0,65 | −0,42 | −0,28 | −0,23 |
| Métodos realmente separables | 22 % | 15 % | 12 % | 35 % | 10 % | 6 % | 18 % | 29 % | 36 % | 39 % |
| Orden de elución correcto (Δ ≥ 2 min) | 99 % | 99 % | 99 % | 93 % | 95 % | 88 % | 87 % | 86 % | 90 % | 89 % |
| Reentrenamiento | | | | | | | v4 rechazado | | v5 aprobado | |

**¿Valió la pena actuar según la predicción? Todavía no, en la métrica de negocio.** El modelo empata con el proceso actual: 0 corridas evitadas en los 10 lotes, porque no aprueba ningún método. Su intervalo por par (unos ±8 min) es mucho más ancho que la separación que necesita el analista (0,5 min). Confiar a ciegas habría costado entre 0,23 y 0,87 corridas **extra** por método.

- **Efecto de los reentrenamientos:** no movieron la métrica de negocio. El v5 baja el RMSE del lote 9 de 3,43 a 2,86 min, pero no lo suficiente para aprobar.
- **Valor actual:** el orden de elución en pares con diferencia predicha de 2 min o más (86–99 %), que orienta la corrida exploratoria.
- **Qué haría falta para generar ahorro:** un RMSE de unos 0,5 min. El techo de ahorro medido es del 19 % de las corridas.

**Coherencia con el pitch.** Este resultado reemplaza el "30 % de ahorro" del PSet 1.

# 10. Limitaciones y siguientes pasos

**Limitaciones.**

- No hay datos de un laboratorio real: la métrica de negocio es un proxy y no hay mL de solvente ni corridas medidas.
- El orden por `EXPERIMENTO_ID` no es un tiempo real.
- Los lotes de un solo laboratorio mezclan deriva con cambio de laboratorio.
- La regla de promoción decide con un solo lote.
- Las corridas del PSet 3 quedaron en el Codespace (`corridas.csv` solo tiene las del registro local) y sus corridas hijas no guardan el modelo.
- Con un RMSE de 2,2–3,4 min la alerta todavía no discrimina los pares que coeluyen: el intervalo es de ±8 min y el analista necesita 0,5 min. Hoy su utilidad se limita al orden de elución (obs. 3.3).
- Las dos pruebas de física (flujo y series homólogas) siguen como defectos conocidos.

**Qué haría primero.**

1. **Calibración por método:** medir 1 o 2 estándares en el método del laboratorio y corregir el desplazamiento antes de predecir. Ataca justo el sesgo de equipo que mostró la simulación, y es el camino más corto hacia un RMSE cercano a 0,5 min.
2. **Piloto antes y después** en un laboratorio, con su bitácora del cromatógrafo y su inventario de solventes (obs. 1.4).
3. **Reentrenar ponderando por experimento** en lugar de por fila, y aplicar la regla de promoción sobre 2 lotes.
4. **Calibrar el intervalo** por modificador y por fabricante antes de habilitar la aprobación.

# Anexos

**A.** Memos de los PSets 1, 2 y 3 (se adjuntan a continuación, sin cambios). **B.** Capturas de la evidencia: Kestra, MLflow, la API y el tablero. **C.** `docs/cambios.md`: observaciones y decisiones actualizadas. Evidencia en CSV dentro de `docs/`: `predicciones.csv`, `monitoreo.csv`, `alertas.csv`, `corridas.csv`, `reentrenamientos.csv` y `rollback.csv`.
