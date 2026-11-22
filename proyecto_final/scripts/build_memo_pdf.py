from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS = PROJECT_ROOT / "docs"
SOURCE = DOCS / "memo_tecnico.md"
OUTPUT = DOCS / "PSet3_memo_Buenaño_Peñafiel.pdf"
ANNEX_OUTPUT = DOCS / "PSet3_anexo_Buenaño_Peñafiel.pdf"
BODY_PAGE_LIMIT = 6
FIGURES = DOCS / "figures"
BENCHMARK_REPORT = DOCS / "llm_benchmark_metrics_20261118T013622Z.json"

FONT = "TimesNewRoman"
FONT_BOLD = "TimesNewRoman-Bold"
FONT_ITALIC = "TimesNewRoman-Italic"
FONT_BOLD_ITALIC = "TimesNewRoman-BoldItalic"
TITLE_SIZE = 14
SUBTITLE_SIZE = 12
BODY_SIZE = 10
TABLE_SIZE = 9
SUBTITLE_COLOR = colors.HexColor("#c00000")

# Times New Roman de Microsoft si está instalada; si no, Liberation Serif,
# que tiene las mismas métricas y cubre símbolos como ≤, √, Δ y σ.
_FONT_CANDIDATES = {
    FONT: ("Times_New_Roman.ttf", "times.ttf", "LiberationSerif-Regular.ttf"),
    FONT_BOLD: ("Times_New_Roman_Bold.ttf", "timesbd.ttf", "LiberationSerif-Bold.ttf"),
    FONT_ITALIC: ("Times_New_Roman_Italic.ttf", "timesi.ttf", "LiberationSerif-Italic.ttf"),
    FONT_BOLD_ITALIC: (
        "Times_New_Roman_Bold_Italic.ttf",
        "timesbi.ttf",
        "LiberationSerif-BoldItalic.ttf",
    ),
}
_FONT_DIRS = (Path("/usr/share/fonts"), Path.home() / ".fonts", Path("/Library/Fonts"))


def _register_fonts() -> None:
    for name, candidates in _FONT_CANDIDATES.items():
        for filename in candidates:
            found = next(
                (
                    path
                    for directory in _FONT_DIRS
                    if directory.is_dir()
                    for path in directory.rglob(filename)
                ),
                None,
            )
            if found:
                pdfmetrics.registerFont(TTFont(name, str(found)))
                break
        else:
            raise FileNotFoundError(
                f"No se encontró Times New Roman ni Liberation Serif para {name}"
            )
    pdfmetrics.registerFontFamily(
        FONT,
        normal=FONT,
        bold=FONT_BOLD,
        italic=FONT_ITALIC,
        boldItalic=FONT_BOLD_ITALIC,
    )


_IMAGE_PATTERN = re.compile(
    r"!\[(?P<caption>.*?)\]\((?P<path>.*?)\)(?:\s*\{width=(?P<width>\d+)%\})?"
)


def _inline(text: str) -> str:
    escaped = html.escape(text.replace("\\|", "|"), quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`(.+?)`", r'<i>\1</i>', escaped)
    return escaped


def _table_rows(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        content = line.strip()
        content = content[1:] if content.startswith("|") else content
        content = content[:-1] if content.endswith("|") and not content.endswith("\\|") else content
        # Split only on unescaped pipes so "\|Z\|" stays inside one cell.
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", content)]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    widths = {len(row) for row in rows}
    if len(widths) > 1:
        raise ValueError(f"Table rows have different column counts {sorted(widths)}: {lines[0][:60]}")
    return rows


def _column_widths(rows: list[list[str]], total_width: float) -> list[float]:
    """Width proportional to each column's text, with a floor for short columns."""
    column_count = len(rows[0])
    weights = []
    for column in range(column_count):
        lengths = sorted(len(row[column]) for row in rows[1:]) or [0]
        typical = lengths[len(lengths) // 2] * 0.5 + lengths[-1] * 0.5
        # Header words should not break mid-word; sqrt keeps long columns from dominating.
        weights.append(max(typical, len(rows[0][column]) * 0.9, 8.0) ** 0.5)
    floor = total_width * (0.12 if column_count <= 5 else 0.09)
    raw = [total_width * weight / sum(weights) for weight in weights]
    widths = [max(width, floor) for width in raw]
    scale = total_width / sum(widths)
    return [width * scale for width in widths]


def _extract_eda_figures() -> None:
    notebook_path = PROJECT_ROOT / "notebooks" / "01_eda.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    FIGURES.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for cell in notebook["cells"]:
        for output in cell.get("outputs", []):
            image = output.get("data", {}).get("image/png")
            if image:
                outputs.setdefault(cell["id"], image)

    expected_cells = {
        "eda_distribution.png": "eda-target-distribution",
        "eda_correlation.png": "eda-correlations",
    }
    image_cells = [
        cell["id"]
        for cell in notebook["cells"]
        if any("image/png" in output.get("data", {}) for output in cell.get("outputs", []))
    ]
    if len(image_cells) < 2:
        raise ValueError(f"Expected two EDA figures in {notebook_path}")
    for name, cell_id in expected_cells.items():
        target_id = cell_id if cell_id in outputs else image_cells[
            0 if name == "eda_distribution.png" else 1
        ]
        (FIGURES / name).write_bytes(
            base64.b64decode(outputs[target_id], validate=True)
        )


def _save_cv_chart() -> None:
    baselines = pd.read_csv(DOCS / "baselines.csv")
    candidates = pd.read_csv(DOCS / "candidatos.csv")
    results = pd.concat([baselines, candidates], ignore_index=True)
    labels = {
        "naive_median": "Mediana global",
        "method_median_proxy": "Mediana condición",
        "ridge": "Ridge",
        "knn": "KNN",
        "mlp": "MLP",
        "random_forest": "Random Forest",
        "hist_gradient_boosting": "HistGradientBoosting",
    }
    results["label"] = results["family"].map(labels)
    results = results.sort_values("cv_rmse_mean", ascending=False)

    fig, ax = plt.subplots(figsize=(8.4, 3.8))
    y = np.arange(len(results))
    ax.barh(
        y,
        results["cv_rmse_mean"],
        xerr=results["cv_rmse_std"],
        color=["#2a9d8f" if row.phase == "candidate" else "#8d99ae" for row in results.itertuples()],
        capsize=3,
    )
    ax.set_yticks(y, results["label"])
    ax.set_xlabel("RMSE CV (min), media ± desviación estándar")
    ax.set_title("Comparación agrupada por compuesto: 5 folds")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES / "cv_all_models.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def _save_tuning_chart() -> None:
    tuning = pd.read_csv(DOCS / "tuning.csv")
    baseline = pd.read_csv(DOCS / "candidatos.csv").set_index("family")
    families = [
        ("random_forest", "Random Forest"),
        ("hist_gradient_boosting", "HistGradientBoosting"),
        ("mlp", "MLP"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.7), sharey=True)
    colors_by_family = ["#457b9d", "#2a9d8f", "#e76f51"]
    for ax, (family, label), color in zip(axes, families, colors_by_family, strict=True):
        trials = tuning.loc[tuning["family"].eq(family)].sort_values("configuration")
        ax.scatter(
            trials["configuration"],
            trials["cv_rmse_mean"],
            color=color,
            s=20,
            alpha=0.8,
        )
        ax.axhline(
            baseline.loc[family, "cv_rmse_mean"],
            color="#333333",
            linestyle="--",
            linewidth=1,
            label="Default",
        )
        best_index = trials["cv_rmse_mean"].idxmin()
        best = trials.loc[best_index]
        ax.scatter(
            [best["configuration"]],
            [best["cv_rmse_mean"]],
            color="#d62828",
            s=30,
            zorder=3,
            label="Mejor tuning",
        )
        ax.set_title(label, fontsize=8)
        ax.set_xlabel("Configuración")
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("RMSE CV (min)")
    axes[-1].legend(fontsize=6, loc="best")
    fig.suptitle("30 configuraciones por familia; línea = modelo default", y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES / "tuning_trials.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def _save_llm_chart() -> None:
    report = json.loads(BENCHMARK_REPORT.read_text(encoding="utf-8"))
    metrics = report["metrics"]
    labels = ["Gemini", "Champion\nHistGradientBoosting", "Challenger\nRandom Forest"]
    rmse = [
        metrics["gemini_rmse_min"],
        metrics["champion_rmse_min"],
        metrics["challenger_rmse_min"],
    ]
    mae = [
        metrics["gemini_mae_min"],
        metrics["champion_mae_min"],
        metrics["challenger_mae_min"],
    ]
    fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.2))
    palette = ["#e76f51", "#2a9d8f", "#457b9d"]
    for ax, values, title in zip(
        axes,
        (rmse, mae),
        ("RMSE (min)", "MAE (min)"),
        strict=True,
    ):
        bars = ax.bar(labels, values, color=palette)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.2)
        ax.tick_params(axis="x", labelsize=6)
        for bar, value in zip(bars, values, strict=True):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=7,
            )
    fig.suptitle("Misma muestra: 50 compuestos distintos del holdout", y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES / "llm_holdout_comparison.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def _prepare_figures() -> None:
    _extract_eda_figures()
    _save_cv_chart()
    _save_tuning_chart()
    _save_llm_chart()


def _image_flowable(match: re.Match, styles, doc):
    relative_path = match.group("path")
    path = (DOCS / relative_path).resolve()
    if not path.is_relative_to(DOCS.resolve()) or not path.is_file():
        raise ValueError(f"Report image is missing or outside docs: {relative_path}")
    width_fraction = int(match.group("width") or 100) / 100
    max_width = doc.width * width_fraction
    max_height = doc.height * (0.24 if width_fraction < 1 else 0.34)
    image = Image(str(path))
    scale = min(max_width / image.imageWidth, max_height / image.imageHeight)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    caption = Paragraph(_inline(match.group("caption")), styles["Caption"])
    return [image, caption]


def _build_story(styles, doc) -> list:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    pages: list[list] = [[]]
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line == r"\newpage":
            # Sections flow continuously to respect the 6-page body limit;
            # only the annex (which does not count) starts on a new page.
            next_line = next(
                (item.strip() for item in lines[index + 1:] if item.strip()), ""
            )
            if next_line.startswith("## Anexo"):
                pages.append([])
            index += 1
            continue
        if line.startswith("!["):
            matches = []
            while index < len(lines) and lines[index].strip().startswith("!["):
                match = _IMAGE_PATTERN.fullmatch(lines[index].strip())
                if not match:
                    raise ValueError(f"Unsupported image syntax: {lines[index]}")
                matches.append(match)
                index += 1
            image_cells = [
                _image_flowable(match, styles, doc) for match in matches
            ]
            if len(image_cells) == 1 and int(matches[0].group("width") or 100) == 100:
                pages[-1].extend(image_cells[0])
            else:
                widths = [
                    doc.width * int(match.group("width") or 100) / 100
                    for match in matches
                ]
                table = Table([image_cells], colWidths=widths, hAlign="LEFT")
                table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 2),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                            ("TOPPADDING", (0, 0), (-1, -1), 2),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                pages[-1].append(table)
            pages[-1].append(Spacer(1, 3))
            continue
        if line.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            text_rows = _table_rows(table_lines)
            if not text_rows:
                continue
            rows = [
                [
                    Paragraph(
                        f"<b>{_inline(cell)}</b>" if row_index == 0 else _inline(cell),
                        styles["MemoTable"],
                    )
                    for cell in row
                ]
                for row_index, row in enumerate(text_rows)
            ]
            table = Table(
                rows,
                colWidths=_column_widths(text_rows, doc.width),
                repeatRows=1,
                hAlign="LEFT",
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce6f1")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17365d")),
                        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7c4")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            pages[-1].extend([Spacer(1, 2), table, Spacer(1, 4)])
            continue
        if line.startswith("- "):
            items = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                item = lines[index].strip()[2:]
                items.append(ListItem(Paragraph(_inline(item), styles["MemoBody"])))
                index += 1
            pages[-1].append(
                ListFlowable(items, bulletType="bullet", leftIndent=12, bulletFontName=FONT, bulletFontSize=BODY_SIZE)
            )
            pages[-1].append(Spacer(1, 2))
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)", line)
        if heading:
            level, text = len(heading.group(1)), heading.group(2)
            style = {
                1: styles["MemoTitle"],
                2: styles["MemoHeading"],
            }.get(level, styles["MemoSubheading"])
            pages[-1].append(Paragraph(_inline(text), style))
            index += 1
            continue

        paragraph_lines = [line]
        index += 1
        while (
            index < len(lines)
            and lines[index].strip()
            and not lines[index].strip().startswith(("#", "|", "- ", "!["))
            and lines[index].strip() != r"\newpage"
        ):
            paragraph_lines.append(lines[index].strip())
            index += 1
        pages[-1].append(
            Paragraph(_inline(" ".join(paragraph_lines)), styles["MemoBody"])
        )
        pages[-1].append(Spacer(1, 2))

    story = []
    for page_index, content in enumerate(pages):
        story.extend(content)
        if page_index < len(pages) - 1:
            story.append(PageBreak())
    return story


def _footer(label: str):
    def draw(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont(FONT, 9)
        canvas.setFillColor(colors.HexColor("#5b6573"))
        canvas.drawString(18 * mm, 10 * mm, label)
        canvas.drawRightString(192 * mm, 10 * mm, f"Página {document.page}")
        canvas.restoreState()

    return draw


_header_footer = _footer("QSRR-Predict · PSet 3")
_annex_footer = _footer("QSRR-Predict · PSet 3 · Anexo")


def _split_annex(story: list) -> tuple[list, list]:
    """Split the story at the PageBreak that precedes the first "Anexo" heading."""
    for position, flowable in enumerate(story):
        if isinstance(flowable, Paragraph) and flowable.getPlainText().startswith("Anexo"):
            body = story[:position]
            while body and isinstance(body[-1], PageBreak):
                body.pop()
            return body, story[position:]
    return story, []


def build_pdf() -> None:
    _register_fonts()
    _prepare_figures()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="MemoTitle",
            parent=styles["Title"],
            fontName=FONT_BOLD,
            fontSize=TITLE_SIZE,
            leading=17,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MemoHeading",
            parent=styles["Heading2"],
            fontName=FONT_BOLD,
            fontSize=TITLE_SIZE,
            leading=17,
            textColor=colors.black,
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MemoSubheading",
            parent=styles["Heading3"],
            fontName=FONT_BOLD,
            fontSize=SUBTITLE_SIZE,
            leading=14.5,
            textColor=SUBTITLE_COLOR,
            spaceBefore=6,
            spaceAfter=3,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MemoBody",
            parent=styles["BodyText"],
            fontName=FONT,
            fontSize=BODY_SIZE,
            leading=12,
            alignment=TA_JUSTIFY,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MemoTable",
            parent=styles["BodyText"],
            fontName=FONT,
            fontSize=TABLE_SIZE,
            leading=10.5,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Caption",
            parent=styles["BodyText"],
            fontName=FONT_ITALIC,
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#404040"),
            spaceAfter=4,
        )
    )

    def make_document(path: Path, title: str) -> SimpleDocTemplate:
        return SimpleDocTemplate(
            str(path),
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=11 * mm,
            bottomMargin=15 * mm,
            title=title,
            author="Jonatan Buenaño",
            initialFontName=FONT,
            initialFontSize=BODY_SIZE,
        )

    document = make_document(OUTPUT, "Documento técnico — QSRR-Predict PSet 3")
    body, annex = _split_annex(_build_story(styles, document))
    document.build(body, onFirstPage=_header_footer, onLaterPages=_header_footer)
    if document.page > BODY_PAGE_LIMIT:
        raise RuntimeError(
            f"El cuerpo tiene {document.page} páginas; la rúbrica permite {BODY_PAGE_LIMIT}."
        )
    print(f"PDF generado: {OUTPUT} ({document.page} páginas)")
    if annex:
        annex_document = make_document(ANNEX_OUTPUT, "Anexo — QSRR-Predict PSet 3")
        annex_document.build(annex, onFirstPage=_annex_footer, onLaterPages=_annex_footer)
        print(f"PDF generado: {ANNEX_OUTPUT} ({annex_document.page} páginas)")

if __name__ == "__main__":
    build_pdf()
