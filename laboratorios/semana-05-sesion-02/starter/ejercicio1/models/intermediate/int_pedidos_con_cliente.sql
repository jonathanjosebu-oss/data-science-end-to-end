-- TODO 3: este modelo lee las tablas crudas por su nombre. Cambialas por
-- los modelos de staging, con ref().
select
    p.id_pedido,
    p.fecha,
    p.categoria,
    p.cantidad * p.precio_unitario as monto_total,
    c.ciudad,
    c.segmento
from {{ ref('stg_pedidos') }} as p
join {{ ref('stg_clientes') }} as c on p.id_cliente = c.id_cliente
