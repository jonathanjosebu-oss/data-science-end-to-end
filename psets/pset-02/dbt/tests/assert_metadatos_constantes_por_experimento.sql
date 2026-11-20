-- Silver colapsa réplicas con max(); eso solo es válido si las condiciones son
-- constantes dentro de cada experimento.
select experimento_id
from {{ ref('int_registros_clasificados') }}
where motivo_exclusion is null
group by experimento_id
having count(distinct coalesce(tipo_columna, '<MISSING>')) > 1
    or count(distinct fase_movil) > 1
    or count(distinct coalesce(to_varchar(flujo_ml_min), '<MISSING>')) > 1
    or count(distinct coalesce(to_varchar(t0_min), '<MISSING>')) > 1
