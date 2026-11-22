-- TODO 1: el modelo de staging es el unico que toca raw_pedidos. Lista
-- las columnas que el resto del proyecto usa, en vez de select *.
select
    id_pedido,
    id_cliente,
    fecha,
    categoria,
    cantidad,
    precio_unitario
from raw_pedidos
