# Descriptores de RepoRT que el modelo no usa

Inventario de lo que RepoRT publica por experimento y que hoy no llega al
modelo. Cobertura medida sobre los **219 experimentos C18** del proyecto
(137 539 filas), commit de RepoRT `420b550`, el 2026-11-22.

- **% filas**: porcentaje de las filas C18 cuyo experimento trae el campo con
  valor (no vacío ni `NA`).
- **Exp. ≠ 0**: experimentos donde el valor es distinto de cero (para aditivos,
  cero = no se usa).

## Lo que el modelo sí usa hoy (16 features)

| Origen | Feature |
|---|---|
| `smiles.std` | 9 descriptores RDKit: peso molecular, LogP, TPSA, donadores/aceptores H, enlaces rotables, anillos, anillos aromáticos, fracción sp3 |
| `eluent.A/B.h2o`, `.meoh`, `.acn` | 6 fracciones de solvente (vía `fase_movil`) |
| `column.flowrate` | flujo (mL/min) |

`column.name` (`tipo_columna`) entra a la API y a la línea base, pero no es feature del modelo.

## A. Ya está en RAW, pero no llega a la OBT ni al modelo

Solo requiere cambiar dbt, Spark y el modelo; la ingesta no cambia.

| Campo | % filas | Distintos | Efecto esperado en la retención |
|---|---:|---:|---|
| `column.t0` (tiempo muerto, min) | 100 (192 exp. ≠ 0) | 25 | **Muy alto**: toda retención escala con t0. Hoy solo filtra `rt > t0`. |
| `column.length` (mm) | 97,9 | 5 | **Alto**: volumen de columna, junto con el flujo. |
| `column.id` (diámetro interno, mm) | 97,9 | 6 | **Alto**: ídem. |
| `column.particle.size` (µm) | 97,9 | 10 | Medio: eficiencia y presión. |
| `column.temperature` (°C) | **35,8** | 14 | Medio (~1–2 %/°C), pero falta en 2/3 de las filas. |
| `column.usp.code` | 100 | **1** | Ninguno: todas son L1 (C18). |
| `classyfire.*` (6 niveles) | — | — | Bajo–medio: familia química, derivable de la estructura. |
| `name`, `formula`, `inchi.std`, `comment` | — | — | Ninguno o fuga: identificadores, no se usan a propósito. |

## B. Está en `metadata.tsv`, pero la ingesta no lo descarga

| Campo | % filas | Exp. ≠ 0 | Efecto esperado |
|---|---:|---:|---|
| `gradient.start.A` / `.B` (%) | 98,5 | 198 / 190 | **Muy alto**: %B inicial del gradiente. |
| `gradient.end.A` / `.B` (%) | 98,5 | 117 / 195 | **Muy alto**: %B final. |
| `eluent.A.pH` | 93,4 | 175 | **Alto** para ácidos y bases (ionización). |
| `eluent.B.pH` | 86,5 | 130 | Alto. |
| `eluent.A.formic` / `.B.formic` (%) | ~94 | 174 / 152 | Medio: fija el pH bajo; es el aditivo más común. |
| `eluent.A.nh4form` / `.B.nh4form` | ~4 | 17 / 5 | Bajo en volumen; relevante en esos métodos. |
| `eluent.A.nh4ac` / `.B.nh4ac` | ~2 | 12 / 4 | Bajo en volumen. |
| `eluent.A.nh4oh` / `.B.nh4oh` | ~1 | 12 / 2 | Bajo en volumen (pH alto). |
| `eluent.A.acetic` / `.B.acetic` | ~0,5 | 10 / 3 | Muy bajo. |
| `eluent.A.trifluoroacetic` / `.B` | ~0,4 | 5 / 1 | Muy bajo (par iónico). |
| `eluent.A.nh4bicarb`, `.nh4f`, `.heptafluorobutyric` | ≤ 1,4 | ≤ 5 | Despreciable en volumen. |
| `eluent.B.iproh`, `eluent.B.acetone` | — | 2 | Despreciable. |
| Unidades `*.unit` | — | — | Necesarias para normalizar los aditivos, no son features. |

**Siempre vacíos o cero en C18** (no aportan): todos los campos de los eluyentes
C y D; hexano, cloroformo, diclorometano, heptano, fosfórico, carbonato de
amonio, trietil/tripropil/tributilamina, N,N-dimetilhexilamina y medrónico en
A y B; `gradient.start.C/D` y `gradient.end.D`.

## C. Archivos completos que no se ingieren

| Archivo | Contenido | Cobertura C18 | Efecto esperado |
|---|---|---|---|
| **`_gradient.tsv`** | Programa por pasos: tiempo, %A–%D y flujo | 199/219 exp. válidos (97,7 % filas); duración mediana 20 min (p10 10, p90 45) | **El más importante**: pendiente, duración, %B inicial y final, tiempo de lavado. Es la causa raíz de que el flujo actúe como proxy del método. No recupera el flujo de los 24 experimentos que no lo tienen. |
| `_descriptors_canonical_success.tsv` | ~287 descriptores moleculares precalculados | — | Medio: podría corregir las series homólogas. |
| `_fingerprints_ecfp6/maccs/pubchem_*` | Huellas estructurales | — | Medio (PSet 1 los incluía en el alcance). |
| `_rtdata_isomeric_success.tsv` | SMILES con estereoquímica | — | Bajo en C18. |
| `_info.tsv` | Tipo de método, fuente, publicación | — | Bajo para predecir; útil para trazabilidad. |
| `_metadata.yaml`, `_report_*.pdf` | Duplicado de metadatos y reportes | — | Ninguno. |

## Prioridad sugerida

1. **`column.t0`, `column.length`, `column.id`, `column.particle.size`**: ya en RAW, ~98–100 % de cobertura.
2. **Gradiente** (`gradient.start/end.B` del metadata + pendiente y duración de `_gradient.tsv`): ~98 % de cobertura, efecto esperado más grande.
3. **pH de A y B y ácido fórmico**: 86–94 % de cobertura.
4. Temperatura: solo 36 % de cobertura; usar con indicador de faltante o descartar.

Ninguno introduce fuga: todos se conocen al diseñar el método, antes de inyectar.
