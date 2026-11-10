with source_data as (
    select * from {{ source('raw_schema', 'RAW_REPORT_DATA') }}
),

renamed_and_cleaned as (
    select
        concat(experiment_id, '_', id) as registro_id,
        trim(name) as nombre_compuesto,
        trim(inchikey_std) as inchikey,
        try_to_double(rt) as tiempo_retencion,
        cast(null as float) as factor_retencion,
        trim(column_name) as tipo_columna,
        concat(
            'A[H2O=', coalesce(to_varchar(eluent_a_h2o), 'NA'),
            '; MeOH=', coalesce(to_varchar(eluent_a_meoh), 'NA'),
            '; ACN=', coalesce(to_varchar(eluent_a_acn), 'NA'),
            '] B[H2O=', coalesce(to_varchar(eluent_b_h2o), 'NA'),
            '; MeOH=', coalesce(to_varchar(eluent_b_meoh), 'NA'),
            '; ACN=', coalesce(to_varchar(eluent_b_acn), 'NA'),
            ']'
        ) as fase_movil,
        try_to_double(column_flowrate) as flujo_ml_min
    from source_data
    where try_to_double(rt) is not null
)

select * from renamed_and_cleaned