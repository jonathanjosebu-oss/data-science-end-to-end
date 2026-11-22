-- TODO 4: este mart devuelve una fila por pedido. Agregalo para que
-- responda cuanto se vendio por ciudad: numero de pedidos y monto total.
select
    ciudad,
    count(*) as numero_pedidos,
    sum(monto_total) as monto_total
from {{ ref('int_pedidos_con_cliente') }}
GROUP BY ciudad
order by monto_total desc