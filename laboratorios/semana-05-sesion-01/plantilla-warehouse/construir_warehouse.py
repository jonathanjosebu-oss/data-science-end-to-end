import duckdb

# TODO: conecta a un archivo .duckdb propio de tu proyecto (se crea solo si no existe).
con = duckdb.connect("TODO.duckdb")

# TODO: reemplaza por la ruta real del archivo que tu pipeline de la Semana 4 genera,
# y por un nombre de tabla propio de tu proyecto.
con.execute("""
    CREATE OR REPLACE TABLE TODO_nombre_tabla AS
    SELECT * FROM read_csv_auto('../data/raw/TODO_archivo.csv')
""")

# TODO: primera consulta, cuántas filas cargaste.
total_filas = con.execute("SELECT COUNT(*) FROM TODO_nombre_tabla").fetchone()[0]
print(f"Filas cargadas: {total_filas}")

# TODO: segunda consulta, una agregación (GROUP BY) que responda una pregunta real de tu proyecto.
resultado = con.execute("""
    SELECT TODO_columna, COUNT(*) AS TODO_alias
    FROM TODO_nombre_tabla
    GROUP BY TODO_columna
    ORDER BY TODO_alias DESC
""").df()
print(resultado)

con.close()
