-- Gold: grano = una fila por (experimento, compuesto) con su tiempo de retención
-- representativo (mediana de réplicas consistentes).
with silver as (
    select * from {{ ref('int_retencion_filtrada') }}
)

select
    md5(registro_id) as hecho_id,
    experimento_id,
    md5(inchikey) as compuesto_id,
    md5(
        concat(
            'tipo=', coalesce(tipo_columna, '<MISSING>'),
            '|fase=', coalesce(fase_movil, '<MISSING>'),
            '|flujo=', coalesce(cast(flujo_ml_min as string), '<MISSING>')
        )
    ) as condicion_id,
    tiempo_retencion,
    n_mediciones,
    rango_replicas_min,
    -- Linaje (PSet 4 §10.6): snapshot de RAW y commit de RepoRT de origen.
    snapshot_date,
    source_commit
from silver
