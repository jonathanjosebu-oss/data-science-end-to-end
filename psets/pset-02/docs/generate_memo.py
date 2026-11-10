#!/usr/bin/env python3
"""Render memo_tecnico.md and its SVG diagrams to the rubric-named PDF."""

import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from svglib.svglib import svg2rlg


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "PSet2_memo_Buenaño_Peñafiel.pdf"
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")

pdfmetrics.registerFont(TTFont("MemoSans", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("MemoSans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(
    TTFont("MemoSans-Oblique", str(FONT_DIR / "DejaVuSans.ttf"))
)
pdfmetrics.registerFont(
    TTFont("MemoMono", str(FONT_DIR / "DejaVuSansMono.ttf"))
)
pdfmetrics.registerFontFamily(
    "MemoSans",
    normal="MemoSans",
    bold="MemoSans-Bold",
    italic="MemoSans-Oblique",
    boldItalic="MemoSans-Bold",
)

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="MemoTitle",
        parent=styles["Title"],
        fontName="MemoSans-Bold",
        fontSize=17,
        leading=21,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#14324b"),
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="MemoH2",
        parent=styles["Heading2"],
        fontName="MemoSans-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#165b78"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="MemoH3",
        parent=styles["Heading3"],
        fontName="MemoSans-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#165b78"),
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="MemoBody",
        parent=styles["BodyText"],
        fontName="MemoSans",
        fontSize=8.6,
        leading=11.2,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="MemoBullet",
        parent=styles["MemoBody"],
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=2,
    )
)
styles.add(
    ParagraphStyle(
        name="MemoTable",
        parent=styles["MemoBody"],
        fontSize=7.2,
        leading=9,
        spaceAfter=0,
    )
)
styles.add(
    ParagraphStyle(
        name="MemoTableHeader",
        parent=styles["MemoTable"],
        fontName="MemoSans-Bold",
        textColor=colors.white,
    )
)
styles.add(
    ParagraphStyle(
        name="MemoCode",
        parent=styles["MemoBody"],
        fontName="MemoMono",
        fontSize=7.8,
        backColor=colors.HexColor("#f1f5f9"),
        borderPadding=3,
    )
)


def markup(text: str) -> str:
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<font name="MemoMono">\1</font>', text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def page_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont("MemoSans", 7)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(18 * mm, 9 * mm, "PSet 2 · Pipeline RepoRT a Snowflake")
    canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Página {doc.page}")
    canvas.restoreState()


def render_diagram(path: Path, available_width: float):
    drawing = svg2rlg(str(path))
    if drawing is None:
        raise RuntimeError(f"No se pudo leer el diagrama SVG: {path.name}")
    max_height = 230 * mm
    scale = min(available_width / drawing.width, max_height / drawing.height)
    drawing.width *= scale
    drawing.height *= scale
    drawing.scale(scale, scale)
    return drawing


def table_from_markdown(lines: list[str], available_width: float):
    records = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        records.append(cells)
    if not records:
        return None

    column_count = len(records[0])
    data = []
    for row_index, row in enumerate(records):
        row += [""] * (column_count - len(row))
        style = "MemoTableHeader" if row_index == 0 else "MemoTable"
        data.append([Paragraph(markup(cell), styles[style]) for cell in row])

    if column_count == 3:
        widths = [available_width * 0.21, available_width * 0.23, available_width * 0.56]
    else:
        widths = [available_width / column_count] * column_count
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#165b78")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
            ]
        )
    )
    return table


def build_story(available_width: float):
    source = (ROOT / "memo_tecnico.md").read_text(encoding="utf-8").splitlines()
    story = []
    paragraph_lines = []
    index = 0

    def flush_paragraph():
        if paragraph_lines:
            text = " ".join(line.strip() for line in paragraph_lines)
            story.append(Paragraph(markup(text), styles["MemoBody"]))
            paragraph_lines.clear()

    while index < len(source):
        line = source[index].rstrip()
        if not line.strip():
            flush_paragraph()
            index += 1
            continue

        if line.startswith("|"):
            flush_paragraph()
            table_lines = []
            while index < len(source) and source[index].lstrip().startswith("|"):
                table_lines.append(source[index])
                index += 1
            table = table_from_markdown(table_lines, available_width)
            if table:
                story.extend([table, Spacer(1, 5)])
            continue

        image_match = re.fullmatch(r"!\[[^]]*]\(([^)]+)\)", line.strip())
        if image_match:
            flush_paragraph()
            story.append(render_diagram(ROOT / image_match.group(1), available_width))
            story.append(Spacer(1, 5))
            index += 1
            continue

        if line.startswith("# "):
            flush_paragraph()
            story.append(Paragraph(markup(line[2:].strip()), styles["MemoTitle"]))
            index += 1
            continue
        if line.startswith("## "):
            flush_paragraph()
            story.append(Paragraph(markup(line[3:].strip()), styles["MemoH2"]))
            index += 1
            continue
        if line.startswith("### "):
            flush_paragraph()
            story.append(Paragraph(markup(line[4:].strip()), styles["MemoH3"]))
            index += 1
            continue
        if line.startswith("- "):
            flush_paragraph()
            story.append(
                Paragraph("• " + markup(line[2:].strip()), styles["MemoBullet"])
            )
            index += 1
            continue
        if re.match(r"\d+\.\s", line):
            flush_paragraph()
            story.append(Paragraph(markup(line.strip()), styles["MemoBullet"]))
            index += 1
            continue

        paragraph_lines.append(line)
        index += 1

    flush_paragraph()
    return story


def main() -> None:
    output = OUTPUT
    page_width, page_height = A4
    left = right = 18 * mm
    top = 16 * mm
    bottom = 20 * mm
    doc = BaseDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=left,
        rightMargin=right,
        topMargin=top,
        bottomMargin=bottom,
        title="PSet 2 — Pipeline de datos end-to-end",
        author="",
    )
    frame = Frame(
        left,
        bottom,
        page_width - left - right,
        page_height - top - bottom,
        id="memo",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="memo", frames=[frame], onPage=page_footer)])
    doc.build(build_story(frame._width))
    print(output)


if __name__ == "__main__":
    main()
