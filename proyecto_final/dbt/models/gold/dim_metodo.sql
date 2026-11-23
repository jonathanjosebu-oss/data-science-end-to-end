-- Gold: una fila por experimento (método cromatográfico) con los descriptores
-- que se conocen al diseñarlo, antes de inyectar: dimensiones de la columna,
-- tiempo muerto, pH de los eluyentes y programa de gradiente (JSON
-- [[t_min, %A, %B, %C, %D, flujo], ...]). Grano: experimento_id.
-- Los atributos son constantes dentro del experimento
-- (assert_metadatos_constantes_por_experimento), por eso max() no mezcla valores.
select
    experimento_id,
    max(t0_min) as t0_min,
    max(columna_longitud_mm) as columna_longitud_mm,
    max(columna_diametro_mm) as columna_diametro_mm,
    max(columna_particula_um) as columna_particula_um,
    max(ph_a) as ph_a,
    max(ph_b) as ph_b,
    max(gradiente) as gradiente
from {{ ref('int_retencion_filtrada') }}
group by experimento_id
