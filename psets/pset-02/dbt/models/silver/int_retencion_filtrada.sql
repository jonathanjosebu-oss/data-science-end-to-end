select
    registro_id,
    nombre_compuesto,
    inchikey,
    tiempo_retencion,
    factor_retencion,
    tipo_columna,
    fase_movil,
    flujo_ml_min
from {{ ref('stg_report_data') }}
where tiempo_retencion > 0