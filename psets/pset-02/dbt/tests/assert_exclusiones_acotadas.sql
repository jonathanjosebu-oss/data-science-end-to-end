-- Guarda contra regresiones: si las reglas de limpieza excluyen más del
-- porcentaje tolerado, el build falla en vez de publicar un Gold recortado.
select
    count_if(motivo_exclusion is not null) / count(*) as fraccion_excluida
from {{ ref('int_registros_clasificados') }}
having count_if(motivo_exclusion is not null) / count(*) > {{ var('fraccion_max_excluida') }}
