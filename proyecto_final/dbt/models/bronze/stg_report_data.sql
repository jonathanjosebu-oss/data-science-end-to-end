-- Bronze: estandariza nombres y tipos de RAW sin descartar filas.
-- RAW conserva un snapshot por fecha lógica (backfill); Bronze toma el snapshot
-- indicado en la variable `snapshot_date` o, por defecto, el más reciente.
with source_data as (
    select * from {{ source('raw_schema', 'RAW_REPORT_DATA') }}
),

snapshot_elegido as (
    -- Exactamente una fila: la fecha pedida o la más reciente.
    {% if var('snapshot_date', none) %}
    select to_date('{{ var("snapshot_date") }}') as snapshot_date
    {% else %}
    select max(snapshot_date) as snapshot_date from source_data
    {% endif %}
)

select
    concat(s.experiment_id, '_', s.id) as registro_id,
    s.experiment_id as experimento_id,
    s.id as medicion_id,
    nullif(trim(s.name), '') as nombre_compuesto,
    nullif(trim(s.inchikey_std), '') as inchikey,
    try_to_double(to_varchar(s.rt)) as tiempo_retencion,
    -- RepoRT usa t0 = 0 cuando el tiempo muerto no fue reportado.
    nullif(try_to_double(to_varchar(s.column_t0)), 0) as t0_min,
    nullif(trim(s.column_name), '') as tipo_columna,
    concat(
        'A[H2O=', coalesce(to_varchar(s.eluent_a_h2o), 'NA'),
        '; MeOH=', coalesce(to_varchar(s.eluent_a_meoh), 'NA'),
        '; ACN=', coalesce(to_varchar(s.eluent_a_acn), 'NA'),
        '] B[H2O=', coalesce(to_varchar(s.eluent_b_h2o), 'NA'),
        '; MeOH=', coalesce(to_varchar(s.eluent_b_meoh), 'NA'),
        '; ACN=', coalesce(to_varchar(s.eluent_b_acn), 'NA'),
        ']'
    ) as fase_movil,
    try_to_double(to_varchar(s.column_flowrate)) as flujo_reportado,
    -- PSet 4: descriptores del método. RepoRT usa 0 cuando no se reportó la
    -- dimensión o el pH (un pH 0 o una columna de 0 mm no son físicos).
    nullif(try_to_double(to_varchar(s.column_length)), 0) as columna_longitud_mm,
    nullif(try_to_double(to_varchar(s.column_id)), 0) as columna_diametro_mm,
    nullif(try_to_double(to_varchar(s.column_particle_size)), 0) as columna_particula_um,
    nullif(try_to_double(to_varchar(s.eluent_a_ph)), 0) as ph_a,
    nullif(try_to_double(to_varchar(s.eluent_b_ph)), 0) as ph_b,
    nullif(trim(s.gradient_program), '') as gradiente,
    s.snapshot_date,
    s.source_commit
from source_data as s
inner join snapshot_elegido as e
    on s.snapshot_date = e.snapshot_date
