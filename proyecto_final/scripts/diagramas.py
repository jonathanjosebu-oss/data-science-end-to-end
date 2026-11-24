"""Diagramas del proyecto final: docs/arquitectura.svg y docs/modelo_dimensional.svg.

    python -m scripts.diagramas            # escribe los SVG
    python -m scripts.diagramas --png      # además los PNG (requiere playwright + Chrome)
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
FUENTE = "Times New Roman, Times, serif"
TINTA, TINTA2, BORDE, FONDO = "#1f1f1f", "#52514e", "#8a8984", "#ffffff"
GRUPOS = {  # relleno suave + borde por capa
    "datos": ("#eaf2fc", "#2a78d6"),
    "modelo": ("#fdeee7", "#eb6834"),
    "servicio": ("#e8f6f0", "#1a8f63"),
    "humano": ("#fdecec", "#c62828"),
}


def caja(x, y, w, h, titulo, lineas, grupo):
    relleno, borde = GRUPOS[grupo]
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{relleno}" stroke="{borde}" stroke-width="1.6"/>',
           f'<text x="{x + w / 2}" y="{y + 22}" text-anchor="middle" font-size="15" font-weight="bold" fill="{TINTA}">{escape(titulo)}</text>']
    for i, linea in enumerate(lineas):
        out.append(f'<text x="{x + w / 2}" y="{y + 42 + 16 * i}" text-anchor="middle" font-size="12.5" fill="{TINTA2}">{escape(linea)}</text>')
    return "\n".join(out)


def flecha(puntos, etiqueta=None, pos=None, discontinua=False, ancla="middle"):
    d = "M " + " L ".join(f"{x} {y}" for x, y in puntos)
    estilo = ' stroke-dasharray="6 4"' if discontinua else ""
    out = [f'<path d="{d}" fill="none" stroke="{TINTA2}" stroke-width="1.6"{estilo} marker-end="url(#punta)"/>']
    if etiqueta:
        x, y = pos
        out.append(f'<text x="{x}" y="{y}" text-anchor="{ancla}" font-size="12" font-style="italic" fill="{TINTA2}">{escape(etiqueta)}</text>')
    return "\n".join(out)


def seccion(y, texto):
    return (f'<text x="30" y="{y}" font-size="16" font-weight="bold" fill="#c62828">{escape(texto)}</text>'
            f'<line x1="30" y1="{y + 8}" x2="1370" y2="{y + 8}" stroke="#e6e5e0" stroke-width="1"/>')


def svg(ancho, alto, titulo, cuerpo):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" viewBox="0 0 {ancho} {alto}" font-family="{FUENTE}" role="img">
<title>{escape(titulo)}</title>
<defs><marker id="punta" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="userSpaceOnUse">
<path d="M0,0 L10,4 L0,8 z" fill="{TINTA2}"/></marker></defs>
<rect width="100%" height="100%" fill="{FONDO}"/>
{cuerpo}
</svg>
"""


def arquitectura() -> str:
    H = 82
    p = [
        f'<text x="700" y="34" text-anchor="middle" font-size="22" font-weight="bold" fill="#c62828">QSRR-Predict · arquitectura end-to-end</text>',
        seccion(70, "1 · Datos (PSet 2) — orquestado por Kestra, almacenado en Snowflake"),
        caja(30, 95, 160, H, "RepoRT", ["GitHub, TSV por", "experimento"], "datos"),
        caja(225, 95, 190, H, "Kestra: ingesta", ["backfill por snapshot,", "retries, commit fuente"], "datos"),
        caja(450, 95, 170, H, "Snowflake RAW", ["RAW_REPORT_DATA", "partición por fecha"], "datos"),
        caja(655, 95, 290, H, "dbt: Bronze → Silver → Gold", ["limpieza auditable, 46 pruebas;", "estrella con dim_metodo"], "datos"),
        caja(980, 95, 200, H, "Spark: OBT", ["OBT_QSRR_FINAL", "grano experimento × compuesto"], "datos"),
        flecha([(190, 136), (225, 136)]), flecha([(415, 136), (450, 136)]),
        flecha([(620, 136), (655, 136)]), flecha([(945, 136), (980, 136)]),

        seccion(232, "2 · Modelo (PSet 3) — experimentación y registro"),
        caja(30, 257, 230, H, "EDA y experimentos", ["notebooks 01–05, split por", "experimento, GroupKFold"], "modelo"),
        caja(295, 257, 230, H, "src/pipeline.py", ["28 features RDKit + método;", "HistGradientBoosting"], "modelo"),
        caja(560, 257, 190, H, "MLflow Tracking", ["corridas, métricas, tags", "de linaje (OBT, Gold)"], "modelo"),
        caja(785, 257, 250, H, "Model Registry", ["qsrr-predict-modelo", "alias @champion / @challenger"], "modelo"),
        flecha([(1080, 177), (1080, 210), (14, 210), (14, 298), (30, 298)], "OBT (snapshot con SHA-256)", (620, 204)),
        flecha([(260, 298), (295, 298)]), flecha([(525, 298), (560, 298)]), flecha([(750, 298), (785, 298)]),

        seccion(410, "3 · Operación (PSet 4)"),
        caja(30, 435, 200, H, "GitHub Actions", ["ci.yml: pytest + imagen", "cd.yml: imagen a GHCR"], "servicio"),
        caja(265, 435, 210, H, "API FastAPI (Docker)", ["/salud /modelo /predecir", "respaldo + interruptor"], "servicio"),
        caja(510, 435, 220, H, "Kestra: produccion_lotes", ["10 lotes → POST /predecir;", "target llega 1 semana después"], "servicio"),
        caja(765, 435, 240, H, "Snowflake PRODUCCION", ["PREDICCIONES · TARGETS", "MONITOREO · ALERTAS"], "servicio"),
        caja(1040, 435, 200, H, "Tablero Streamlit", ["sistema, modelo, deriva;", "alertas y reentrenamientos"], "servicio"),
        caja(765, 600, 240, H, "Kestra: monitoreo", ["PSI calibrado + KS / chi²,", "RMSE y sesgo por lote"], "servicio"),
        caja(1040, 600, 300, H, "Kestra: reentrenamiento", ["disparo: caída en 2 lotes seguidos;", "challenger, regla, PAUSA humana"], "humano"),
        flecha([(230, 476), (265, 476)]),
        flecha([(510, 476), (475, 476)]),
        flecha([(730, 476), (765, 476)]),
        flecha([(1005, 476), (1040, 476)]),
        flecha([(885, 517), (885, 600)], "cada semana", (893, 563), ancla="start"),
        flecha([(1005, 641), (1040, 641)]),
        flecha([(1300, 600), (1300, 298), (1035, 298)], "aprobado: mueve @champion", (1292, 572), ancla="end"),
        flecha([(910, 339), (910, 395), (430, 395), (430, 435)], "carga models:/…@champion (TTL 30 s, sin reconstruir la imagen)", (670, 389), discontinua=True),
        f'<text x="30" y="740" font-size="12.5" fill="{TINTA2}">Trazabilidad: cada fila de PREDICCIONES guarda versión y run_id; la corrida de MLflow guarda el snapshot de la OBT, su SHA-256, el commit de RepoRT y las tablas Gold.</text>',
        f'<text x="30" y="760" font-size="12.5" fill="{TINTA2}">El código se despliega solo (CD); el modelo cambia únicamente cuando una persona aprueba el challenger en la pausa de Kestra.</text>',
    ]
    return svg(1400, 780, "Arquitectura end-to-end QSRR-Predict", "\n".join(p))


def tabla_er(x, y, w, nombre, filas, grupo, grano):
    relleno, borde = GRUPOS[grupo]
    alto = 34 + 19 * len(filas) + 26
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{alto}" rx="6" fill="#ffffff" stroke="{borde}" stroke-width="1.8"/>',
           f'<rect x="{x}" y="{y}" width="{w}" height="30" rx="6" fill="{relleno}" stroke="{borde}" stroke-width="1.8"/>',
           f'<text x="{x + 12}" y="{y + 21}" font-size="15" font-weight="bold" fill="{TINTA}">{escape(nombre)}</text>']
    for i, (col, tipo, clave) in enumerate(filas):
        yy = y + 50 + 19 * i
        marca = {"PK": "#c62828", "FK": "#2a78d6"}.get(clave)
        if marca:
            out.append(f'<text x="{x + 12}" y="{yy}" font-size="11" font-weight="bold" fill="{marca}">{clave}</text>')
        out.append(f'<text x="{x + 40}" y="{yy}" font-size="13" fill="{TINTA}">{escape(col)}</text>')
        out.append(f'<text x="{x + w - 12}" y="{yy}" text-anchor="end" font-size="12" fill="{TINTA2}">{escape(tipo)}</text>')
    out.append(f'<text x="{x + 12}" y="{y + alto - 9}" font-size="11.5" font-style="italic" fill="{TINTA2}">Grano: {escape(grano)}</text>')
    return "\n".join(out), alto


def modelo_dimensional() -> str:
    hecho, h_alto = tabla_er(400, 200, 390, "GOLD.FACT_RETENCION_CROMATOGRAFICA", [
        ("hecho_id", "varchar", "PK"), ("experimento_id", "varchar", "FK"), ("compuesto_id", "varchar", "FK"),
        ("condicion_id", "varchar", "FK"), ("tiempo_retencion", "float (min)", None), ("n_mediciones", "int", None),
        ("rango_replicas_min", "float", None), ("snapshot_date", "date", None), ("source_commit", "varchar", None),
    ], "modelo", "experimento × compuesto (réplicas → mediana)")
    comp, _ = tabla_er(30, 60, 300, "GOLD.DIM_COMPUESTO", [
        ("compuesto_id", "varchar", "PK"), ("inchikey", "varchar", None), ("nombre_compuesto", "varchar", None),
    ], "datos", "compuesto (InChIKey)")
    cond, _ = tabla_er(30, 420, 300, "GOLD.DIM_CONDICIONES", [
        ("condicion_id", "varchar", "PK"), ("tipo_columna", "varchar", None), ("fase_movil", "varchar", None),
        ("flujo_ml_min", "float", None),
    ], "datos", "columna × fase móvil × flujo")
    metodo, _ = tabla_er(860, 200, 300, "GOLD.DIM_METODO", [
        ("experimento_id", "varchar", "PK"), ("t0_min", "float", None), ("columna_longitud_mm", "float", None),
        ("columna_diametro_mm", "float", None), ("columna_particula_um", "float", None), ("ph_a", "float", None),
        ("ph_b", "float", None), ("gradiente", "json", None),
    ], "servicio", "experimento (PSet 4)")
    obt = ('<rect x="860" y="470" width="300" height="88" rx="6" fill="#fdecec" stroke="#c62828" stroke-width="1.6"/>'
           '<text x="1010" y="494" text-anchor="middle" font-size="15" font-weight="bold" fill="#1f1f1f">GOLD.OBT_QSRR_FINAL (Spark)</text>'
           '<text x="1010" y="514" text-anchor="middle" font-size="12.5" fill="#52514e">hecho ⋈ 3 dimensiones + SMILES de RAW</text>'
           '<text x="1010" y="532" text-anchor="middle" font-size="12.5" fill="#52514e">valida unicidad y huérfanos antes del join</text>'
           '<text x="1010" y="550" text-anchor="middle" font-size="12.5" fill="#52514e">grano: experimento × compuesto</text>')
    p = [
        '<text x="595" y="32" text-anchor="middle" font-size="22" font-weight="bold" fill="#c62828">Modelo dimensional (capa Gold)</text>',
        comp, cond, hecho, metodo, obt,
        flecha([(400, 283), (365, 283), (365, 112), (330, 112)]),
        flecha([(400, 302), (365, 302), (365, 472), (330, 472)]),
        flecha([(790, 264), (860, 264)]),
        flecha([(595, 200 + h_alto), (595, 514), (860, 514)], "alimenta", (730, 506), discontinua=True),
    ]
    return svg(1190, 600, "Modelo dimensional Gold", "\n".join(p))


def a_png(svg_path: Path, png_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        pg = b.new_page(device_scale_factor=2)
        pg.goto(svg_path.as_uri())
        pg.locator("svg").screenshot(path=str(png_path))
        b.close()


if __name__ == "__main__":
    salidas = {"arquitectura": arquitectura(), "modelo_dimensional": modelo_dimensional()}
    for nombre, contenido in salidas.items():
        ruta = DOCS / f"{nombre}.svg"
        ruta.write_text(contenido, encoding="utf-8")
        print("Escrito", ruta)
        if "--png" in sys.argv:
            a_png(ruta, DOCS / f"{nombre}.png")
            print("Escrito", DOCS / f"{nombre}.png")
