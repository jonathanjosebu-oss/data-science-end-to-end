with silver as (
    select * from {{ ref('int_retencion_filtrada') }}
)

select
    md5(concat(cast(registro_id as string), '_', inchikey)) as hecho_id,
    md5(inchikey) as compuesto_id,
    md5(
        concat(
            'tipo=', coalesce(tipo_columna, '<MISSING>'),
            '|fase=', coalesce(fase_movil, '<MISSING>'),
            '|flujo=', coalesce(cast(flujo_ml_min as string), '<MISSING>')
        )
    ) as condicion_id,
    tiempo_retencion,
    factor_retencion
from silver