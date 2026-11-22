-- Silver (auditoría): una fila por registro Bronze con su decisión de limpieza.
-- `motivo_exclusion` es nulo cuando la fila pasa a Silver; así cada exclusión es
-- trazable y las pruebas pueden verificar que no se pierden ni crean filas.
with bronze as (
    select * from {{ ref('stg_report_data') }}
),

normalizado as (
    select
        *,
        -- Unidades de flujo: RepoRT reporta mL/min. Un valor > flujo_max_ml_min es
        -- físicamente implausible en HPLC/UHPLC y se interpreta como µL/min.
        case
            when flujo_reportado is null or flujo_reportado <= 0 then null
            when flujo_reportado > {{ var('flujo_max_ml_min') }} then flujo_reportado / 1000
            else flujo_reportado
        end as flujo_ml_min,
        coalesce(flujo_reportado > {{ var('flujo_max_ml_min') }}, false) as flujo_convertido_desde_ul,
        case
            when tiempo_retencion is null or tiempo_retencion <= 0 then 'rt_no_positivo'
            when inchikey is null then 'sin_inchikey'
            when t0_min is not null and tiempo_retencion <= t0_min then 'no_retenido_rt_menor_igual_t0'
            when tiempo_retencion > {{ var('rt_max_min') }} then 'rt_fuera_de_rango'
        end as motivo_fila
    from bronze
),

replicas as (
    -- Compuestos repetidos: mismo InChIKey medido más de una vez en el mismo
    -- experimento. Solo se evalúan las filas que superaron las reglas por fila.
    select
        experimento_id,
        inchikey,
        count(*) as n_mediciones,
        max(tiempo_retencion) - min(tiempo_retencion) as rango_replicas_min
    from normalizado
    where motivo_fila is null
    group by experimento_id, inchikey
)

select
    n.registro_id,
    n.experimento_id,
    n.medicion_id,
    n.nombre_compuesto,
    n.inchikey,
    n.tiempo_retencion,
    n.t0_min,
    n.tipo_columna,
    n.fase_movil,
    n.flujo_reportado,
    n.flujo_ml_min,
    n.flujo_convertido_desde_ul,
    r.n_mediciones,
    r.rango_replicas_min,
    coalesce(
        n.motivo_fila,
        case
            when r.rango_replicas_min > {{ var('rango_max_replicas_min') }}
                then 'replicas_inconsistentes'
        end
    ) as motivo_exclusion,
    n.snapshot_date,
    n.source_commit
from normalizado as n
left join replicas as r
    on n.experimento_id = r.experimento_id
    and n.inchikey = r.inchikey
    and n.motivo_fila is null
