-- Gold no pierde ni duplica observaciones de Silver.
with conteos as (
    select
        (select count(*) from {{ ref('int_retencion_filtrada') }}) as filas_silver,
        (select count(*) from {{ ref('fact_retencion_cromatografica') }}) as filas_hecho
)
select * from conteos
where filas_silver != filas_hecho
