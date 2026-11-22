"""pytest lee este archivo antes de correr las pruebas de psets/proyecto/.

Su presencia deja psets/proyecto/ en la ruta de importacion de las pruebas:
asi una prueba de servicio/ puede escribir from modelado.pipeline_proyecto
import ..., igual que el servicio cuando corre desde psets/proyecto/.
No hace falta agregarle codigo.
"""
