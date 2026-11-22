-- Regla de dominio: un compuesto retenido eluye después del tiempo muerto.
select registro_id, tiempo_retencion, t0_min
from {{ ref('int_retencion_filtrada') }}
where t0_min is not null
  and tiempo_retencion <= t0_min
