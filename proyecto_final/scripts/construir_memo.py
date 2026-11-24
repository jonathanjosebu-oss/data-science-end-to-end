"""Documento técnico del PSet 4: docs/memo_pset4.md -> docs/PSet4_memo_Buenaño_Peñafiel.pdf

    python -m scripts.construir_memo [--video URL]

Formato: todo en Times New Roman; títulos en rojo, negrita, 14 pt; subtítulos en
rojo, negrita, 12 pt; el resto del texto en negro, 10 pt. El cuerpo no debe pasar
de 12 páginas. Anexos: A) memos de los PSets 1–3 (docs/historial), B) capturas
(docs/capturas), C) docs/cambios.md.
"""

from __future__ import annotations

import argparse
import re
import tempfile
from html import escape
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
FUENTE_MD = DOCS / "memo_pset4.md"
SALIDA = DOCS / "PSet4_memo_Buenaño_Peñafiel.pdf"
CAPTURA_CI = DOCS / "capturas" / "github_actions_ci_cd.png"
LIMITE_PAGINAS = 12
ROJO, NEGRO = colors.HexColor("#c00000"), colors.black
ANCHO = A4[0] - 4 * cm

CAPTURAS = [  # anexo B: (archivo, pie)
    ("api_02_respuestas.png", "API: /modelo, una predicción válida (200) y una entrada inválida rechazada (422)."),
    ("api_01_endpoints.png", "API: endpoints documentados (OpenAPI)."),
    ("kestra_01_flujos.png", "Kestra: flujos del namespace qsrr.proyecto."),
    ("kestra_02_ingesta_hasta_obt.png", "Kestra: ingesta de RepoRT hasta la OBT (dbt y Spark)."),
    ("kestra_03_produccion_lotes.png", "Kestra: produccion_lotes, 11 semanas de simulación."),
    ("kestra_04_alerta_monitoreo_semana8.png", "Kestra: monitoreo de la semana 8; alertas de RMSE y sesgo por la deriva inducida."),
    ("kestra_05_reentrenamiento_rechazado.png", "Kestra: reentrenamiento de la semana 8 (v4); la regla no promueve. Los ERROR son avisos de git en stderr."),
    ("kestra_08_reentrenamiento_aprobado_comparacion.png", "Kestra: reentrenamiento de la semana 10 (v5); la regla recomienda promover."),
    ("kestra_06_reentrenamiento_topologia.png", "Kestra: entrenar, comparar, pausa de aprobación y decidir."),
    ("mlflow_01_registro_aliases.png", "MLflow: versiones con su motivo, decisión humana y alias champion en v5."),
    ("mlflow_02_corridas.png", "MLflow: corridas del experimento qsrr-predict-c18."),
    ("tablero_03_desempeno_negocio.png", "Tablero: desempeño y negocio por lote, con alertas y reentrenamientos."),
    ("tablero_04_deriva.png", "Tablero: PSI por descriptor y guardia de dominio."),
    ("tablero_05_alertas.png", "Tablero: alertas y ciclos de reentrenamiento."),
    ("tablero_01_sistema.png", "Tablero: latencia, errores y volumen por semana."),
]


def registrar_fuentes() -> None:
    carpetas = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts"), Path.home() / ".fonts", Path("/Library/Fonts")]
    nombres = {"Times": ("times.ttf", "Times_New_Roman.ttf", "LiberationSerif-Regular.ttf"),
               "Times-B": ("timesbd.ttf", "Times_New_Roman_Bold.ttf", "LiberationSerif-Bold.ttf"),
               "Times-I": ("timesi.ttf", "Times_New_Roman_Italic.ttf", "LiberationSerif-Italic.ttf"),
               "Times-BI": ("timesbi.ttf", "Times_New_Roman_Bold_Italic.ttf", "LiberationSerif-BoldItalic.ttf")}
    for nombre, candidatos in nombres.items():
        ruta = next((p for c in carpetas if c.is_dir() for f in candidatos for p in c.rglob(f)), None)
        if ruta is None:
            raise FileNotFoundError(f"No se encontró Times New Roman para {nombre}")
        pdfmetrics.registerFont(TTFont(f"TNR-{nombre}", str(ruta)))
    pdfmetrics.registerFontFamily("TNR-Times", normal="TNR-Times", bold="TNR-Times-B", italic="TNR-Times-I",
                                  boldItalic="TNR-Times-BI")


def estilos() -> dict[str, ParagraphStyle]:
    base = dict(fontName="TNR-Times", textColor=NEGRO, fontSize=10, leading=12.6)
    return {
        "titulo": ParagraphStyle("titulo", fontName="TNR-Times-B", fontSize=14, leading=17, textColor=ROJO,
                                 spaceBefore=10, spaceAfter=5, keepWithNext=True),
        "subtitulo": ParagraphStyle("subtitulo", fontName="TNR-Times-B", fontSize=12, leading=15, textColor=ROJO,
                                    spaceBefore=6, spaceAfter=3, keepWithNext=True),
        "portada": ParagraphStyle("portada", fontName="TNR-Times-B", fontSize=14, leading=17, textColor=ROJO,
                                  alignment=TA_CENTER, spaceAfter=3),
        "cabecera": ParagraphStyle("cabecera", **base, alignment=TA_CENTER),
        "cuerpo": ParagraphStyle("cuerpo", **base, alignment=TA_JUSTIFY, spaceAfter=5),
        "celda": ParagraphStyle("celda", **base),
        "etiqueta": ParagraphStyle("etiqueta", **base, spaceAfter=3, keepWithNext=True),
        "pie": ParagraphStyle("pie", **{**base, "fontName": "TNR-Times-I"}, alignment=TA_CENTER, spaceAfter=6),
    }


def en_linea(texto: str) -> str:
    texto = escape(texto, quote=False)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", texto)
    return re.sub(r"`(.+?)`", r"<i>\1</i>", texto)


def tabla(filas: list[str], E) -> Table:
    celdas = [[c.strip() for c in f.strip().strip("|").split("|")] for f in filas]
    celdas = [f for f in celdas if not all(re.fullmatch(r":?-{3,}:?", c) for c in f)]
    datos = [[Paragraph(("<b>%s</b>" if i == 0 else "%s") % en_linea(c), E["celda"]) for c in f] for i, f in enumerate(celdas)]
    n = len(celdas[0])
    limpio = lambda c: re.sub(r"[*`]", "", c)
    # Mínimo: la palabra más larga de la columna (en negrita, por la cabecera) no se parte.
    minimos = [max(pdfmetrics.stringWidth(p, "TNR-Times-B", 10) for f in celdas for p in limpio(f[j]).split() or [""]) + 8
               for j in range(n)]
    largos = [max(len(limpio(f[j])) for f in celdas) for j in range(n)]
    pesos = [min(max(l, 4), 60) for l in largos]
    if sum(minimos) >= ANCHO:  # no caben ni los mínimos: reparto proporcional y se parten palabras
        anchos = [ANCHO * m / sum(minimos) for m in minimos]
    else:
        anchos = [max(ANCHO * p / sum(pesos), m) for p, m in zip(pesos, minimos)]
        exceso = sum(anchos) - ANCHO
        holgura = [a - m for a, m in zip(anchos, minimos)]
        if exceso > 0:  # se recorta solo la holgura sobre el mínimo, en proporción
            anchos = [a - exceso * h / sum(holgura) for a, h in zip(anchos, holgura)]
    t = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9a9a9a")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#efefef")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def imagen(ruta: Path, ancho_rel: float, alto_max: float = 22 * cm) -> Image:
    w, h = ImageReader(str(ruta)).getSize()
    ancho = ANCHO * ancho_rel
    alto = ancho * h / w
    if alto > alto_max:
        alto, ancho = alto_max, alto_max * w / h
    return Image(str(ruta), width=ancho, height=alto)


def markdown_a_flujo(texto: str, E, video: str) -> list:
    texto = texto.replace("{{VIDEO}}", video)
    flujo: list = []
    lineas = texto.splitlines()
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        if linea.startswith("% "):
            estilo = "portada" if not flujo else "cabecera"
            flujo.append(Paragraph(en_linea(linea[2:]), E[estilo]))
            if i + 1 < len(lineas) and not lineas[i + 1].startswith("% "):
                flujo.append(Spacer(1, 6))
        elif linea.startswith("# "):
            flujo.append(Paragraph(en_linea(linea[2:]), E["titulo"]))
        elif linea.startswith("## "):
            flujo.append(Paragraph(en_linea(linea[3:]), E["subtitulo"]))
        elif linea.strip() == "{{CAPTURA_CI}}":
            if CAPTURA_CI.exists():
                flujo += [imagen(CAPTURA_CI, 0.95, 9 * cm),
                          Paragraph("GitHub Actions: CI en verde y la imagen publicada en GHCR por cd.yml.", E["pie"])]
            else:
                flujo.append(Paragraph("<b>[Pendiente]</b> Captura de GitHub Actions en verde con la imagen publicada en GHCR "
                                       f"(se agrega como docs/capturas/{CAPTURA_CI.name} tras el merge a master).", E["cuerpo"]))
        elif m := re.match(r"!\[(.*?)\]\((.*?)\)(?:\{width=(\d+)\})?", linea):
            pie, ruta, ancho = m.group(1), RAIZ / m.group(2), int(m.group(3) or 100) / 100
            flujo.append(KeepTogether([imagen(ruta, ancho), Paragraph(en_linea(pie), E["pie"])]))
        elif linea.startswith("|"):
            bloque = []
            while i < len(lineas) and lineas[i].startswith("|"):
                bloque.append(lineas[i]); i += 1
            flujo += [tabla(bloque, E), Spacer(1, 6)]
            continue
        elif re.match(r"^(\s*)(- |\d+\. )", linea):
            items, numerada = [], bool(re.match(r"^\s*\d+\. ", linea))
            while i < len(lineas) and re.match(r"^(\s*)(- |\d+\. )", lineas[i]):
                sangria = len(lineas[i]) - len(lineas[i].lstrip())
                contenido = re.sub(r"^\s*(- |\d+\. )", "", lineas[i])
                items.append(ListItem(Paragraph(en_linea(contenido), E["cuerpo"]), leftIndent=12 + sangria * 6))
                i += 1
            flujo.append(ListFlowable(items, bulletType="1" if numerada else "bullet", bulletFontName="TNR-Times",
                                      bulletFontSize=10, start="1" if numerada else "•", leftIndent=14))
            continue
        elif linea.strip():
            parrafo = [linea.strip()]
            while i + 1 < len(lineas) and lineas[i + 1].strip() and not re.match(r"^(#|\||!\[|%|\s*- |\s*\d+\. |\{\{)", lineas[i + 1]):
                i += 1; parrafo.append(lineas[i].strip())
            texto_p = " ".join(parrafo)
            etiqueta = re.fullmatch(r"\*\*[^*]+\*\*", texto_p) is not None  # "**Lotes.**" sola, antes de una lista
            flujo.append(Paragraph(en_linea(texto_p), E["etiqueta" if etiqueta else "cuerpo"]))
        i += 1
    return unir_titulos(flujo, E)


def unir_titulos(flujo: list, E) -> list:
    """Un título nunca queda solo al pie de página: viaja con el bloque siguiente."""
    salida, i = [], 0
    titulos = (E["titulo"], E["subtitulo"])
    while i < len(flujo):
        item = flujo[i]
        if isinstance(item, Paragraph) and (item.style in titulos or item.style is E["etiqueta"]) and i + 1 < len(flujo):
            grupo = [item]
            while i + 1 < len(flujo) and isinstance(flujo[i + 1], Paragraph) and flujo[i + 1].style in titulos:
                i += 1; grupo.append(flujo[i])
            if i + 1 < len(flujo):
                i += 1; grupo.append(flujo[i])
            salida.append(KeepTogether(grupo))
        else:
            salida.append(item)
        i += 1
    return salida


def pie_de_pagina(texto: str):
    def dibujar(canvas, doc):
        canvas.saveState()
        canvas.setFont("TNR-Times", 10)
        canvas.setFillColor(NEGRO)
        canvas.drawCentredString(A4[0] / 2, 1.2 * cm, f"{texto} · página {doc.page}")
        canvas.restoreState()
    return dibujar


def construir(flujo: list, ruta: Path, pie: str) -> int:
    doc = SimpleDocTemplate(str(ruta), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=2 * cm, title="PSet 4 · Documento técnico QSRR-Predict",
                            author="Jonatan Buenaño Peñafiel")
    f = pie_de_pagina(pie)
    doc.build(flujo, onFirstPage=f, onLaterPages=f)
    return len(PdfReader(str(ruta)).pages)


def anexo_b_c(E) -> list:
    flujo: list = [Paragraph("Anexo B · Capturas de la evidencia", E["titulo"])]
    for archivo, pie in CAPTURAS:
        ruta = DOCS / "capturas" / archivo
        if ruta.exists():
            flujo.append(KeepTogether([imagen(ruta, 1.0, 11.5 * cm), Paragraph(en_linea(pie), E["pie"])]))
    if CAPTURA_CI.exists():
        flujo.append(KeepTogether([imagen(CAPTURA_CI, 1.0, 11.5 * cm), Paragraph("GitHub Actions y GHCR.", E["pie"])]))
    flujo += [PageBreak(), Paragraph("Anexo C · docs/cambios.md", E["titulo"])]
    cambios = (DOCS / "cambios.md").read_text(encoding="utf-8").replace("# Registro de cambios", "## Registro de cambios", 1)
    # Times New Roman no tiene glifos para los íconos de estado.
    for icono, texto in (("✅", "Hecho"), ("⏳", "Pendiente"), ("🟡", "Parcial")):
        cambios = cambios.replace(icono, texto)
    flujo += markdown_a_flujo(cambios, E, "")
    return flujo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="pendiente (se agrega al publicar el video)")
    args = parser.parse_args()
    registrar_fuentes()
    E = estilos()
    pie = "QSRR-Predict · PSet 4 · Buenaño Peñafiel"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cuerpo = markdown_a_flujo(FUENTE_MD.read_text(encoding="utf-8"), E, en_linea(args.video))
        n_cuerpo = construir(cuerpo, tmp / "cuerpo.pdf", pie)
        construir([Spacer(1, 8 * cm), Paragraph("Anexo A · Memos de los PSets 1, 2 y 3", E["portada"]),
                   Paragraph("Entregas originales, sin cambios: PSet 1 (memo y pitch), PSet 2 y PSet 3. "
                             "Sus correcciones están en el anexo C.", E["cabecera"])], tmp / "sep_a.pdf", "QSRR-Predict · PSet 4 · Anexo A")
        construir(anexo_b_c(E), tmp / "anexo_bc.pdf", "QSRR-Predict · PSet 4 · Anexos B y C")
        escritor = PdfWriter()
        partes = [tmp / "cuerpo.pdf", tmp / "sep_a.pdf", *sorted((DOCS / "historial").glob("PSet*_*.pdf")), tmp / "anexo_bc.pdf"]
        for parte in partes:
            escritor.append(str(parte))
        escritor.add_metadata({"/Title": "PSet 4 · Documento técnico QSRR-Predict", "/Author": "Jonatan Buenaño Peñafiel"})
        with open(SALIDA, "wb") as fh:
            escritor.write(fh)
    total = len(PdfReader(str(SALIDA)).pages)
    estado = "OK" if n_cuerpo <= LIMITE_PAGINAS else f"EXCEDE el límite de {LIMITE_PAGINAS}"
    print(f"{SALIDA.name}: cuerpo {n_cuerpo} páginas ({estado}); total con anexos {total}")


if __name__ == "__main__":
    main()
