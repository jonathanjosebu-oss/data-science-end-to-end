-- Silver: una observación por (experimento, compuesto). Aplica las reglas de
-- limpieza documentadas en int_registros_clasificados y colapsa las réplicas
-- consistentes (rango <= rango_max_replicas_min) en su mediana.
with conservadas as (
    select * from {{ ref('int_registros_clasificados') }}
    where motivo_exclusion is null
)

select
    concat(experimento_id, '_', inchikey) as registro_id,
    experimento_id,
    inchikey,
    min(nombre_compuesto) as nombre_compuesto,
    median(tiempo_retencion) as tiempo_retencion,
    count(*) as n_mediciones,
    max(tiempo_retencion) - min(tiempo_retencion) as rango_replicas_min,
    -- Columna, fase móvil, flujo y t0 son metadatos por experimento: constantes
    -- dentro del grupo (lo verifica assert_metadatos_constantes_por_experimento).
    max(t0_min) as t0_min,
    max(tipo_columna) as tipo_columna,
    max(fase_movil) as fase_movil,
    max(flujo_ml_min) as flujo_ml_min,
    max(snapshot_date) as snapshot_date,
    max(source_commit) as source_commit
from conservadas
group by experimento_id, inchikey
