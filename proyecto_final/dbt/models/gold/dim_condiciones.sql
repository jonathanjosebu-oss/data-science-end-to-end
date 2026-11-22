with silver as (
    select distinct
        tipo_columna,
        fase_movil,
        flujo_ml_min
    from {{ ref('int_retencion_filtrada') }}
)

select
    md5(
        concat(
            'tipo=', coalesce(tipo_columna, '<MISSING>'),
            '|fase=', coalesce(fase_movil, '<MISSING>'),
            '|flujo=', coalesce(cast(flujo_ml_min as string), '<MISSING>')
        )
    ) as condicion_id,
    tipo_columna,
    fase_movil,
    flujo_ml_min
from silver