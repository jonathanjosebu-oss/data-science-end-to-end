-- Conservación Bronze -> auditoría -> Silver: toda fila Bronze recibe una
-- decisión, y las filas conservadas suman exactamente las mediciones de Silver.
with conteos as (
    select
        (select count(*) from {{ ref('stg_report_data') }}) as filas_bronze,
        (select count(*) from {{ ref('int_registros_clasificados') }}) as filas_auditadas,
        (select count(*) from {{ ref('int_registros_clasificados') }}
          where motivo_exclusion is null) as filas_conservadas,
        (select sum(n_mediciones) from {{ ref('int_retencion_filtrada') }}) as mediciones_silver
)
select *
from conteos
where filas_bronze != filas_auditadas
   or filas_conservadas != mediciones_silver
