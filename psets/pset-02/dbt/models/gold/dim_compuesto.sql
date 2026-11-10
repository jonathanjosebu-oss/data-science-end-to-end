select
    md5(inchikey) as compuesto_id,
    inchikey,
    min(nombre_compuesto) as nombre_compuesto
from {{ ref('int_retencion_filtrada') }}
where inchikey is not null
group by inchikey