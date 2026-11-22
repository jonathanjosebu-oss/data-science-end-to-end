-- Bronze procesa exactamente un snapshot de RAW, completo: mismas filas que
-- esa partición, sin multiplicarlas ni mezclar fechas.
with bronze as (
    select count(*) as filas, count(distinct snapshot_date) as snapshots,
           max(snapshot_date) as snapshot_date
    from {{ ref('stg_report_data') }}
),
raw as (
    select snapshot_date, count(*) as filas
    from {{ source('raw_schema', 'RAW_REPORT_DATA') }}
    group by snapshot_date
)
select b.*
from bronze as b
left join raw as r on r.snapshot_date = b.snapshot_date
where b.snapshots != 1 or b.filas != r.filas or r.filas is null
