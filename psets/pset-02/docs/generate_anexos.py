"""Genera PSet2_anexos_Buenaño_Peñafiel.pdf con evidencia de ejecución del pipeline.

Uso:
    python docs/generate_anexos.py            # arma el PDF con docs/evidencia/*.json
    python docs/generate_anexos.py --refresh  # vuelve a recolectar la evidencia

`--refresh` consulta la API de Kestra (KESTRA_URL, por defecto http://localhost:8080,
con KESTRA_USER/KESTRA_PASSWORD), descarga el run_results.json que Kestra guarda para
la tarea dbt_build y ejecuta consultas de solo lectura en Snowflake con las variables
de `.env` (exportadas en la terminal). No escribe credenciales en los JSON.

Las capturas de pantalla se toman manualmente y se guardan en `docs/capturas/`
(PNG o JPG). Se incluyen en orden alfabético; el nombre del archivo sin prefijo
numérico se usa como pie de figura, p. ej. `01_kestra_ejecucion_exitosa.png`, salvo
que `docs/capturas/pies.json` defina un pie para ese archivo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DOCS = Path(__file__).resolve().parent
PSET = DOCS.parent
EVIDENCE = DOCS / "evidencia"
CAPTURES = DOCS / "capturas"
OUTPUT = DOCS / "PSet2_anexos_Buenaño_Peñafiel.pdf"
FLOW = "ingest_report_to_snowflake"
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")

pdfmetrics.registerFont(TTFont("AnexoSans", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("AnexoSans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("AnexoMono", str(FONT_DIR / "DejaVuSansMono.ttf")))
pdfmetrics.registerFontFamily(
    "AnexoSans",
    normal="AnexoSans",
    bold="AnexoSans-Bold",
    italic="AnexoSans",
    boldItalic="AnexoSans-Bold",
)

NAVY = colors.HexColor("#17365d")
STYLES = {
    "title": ParagraphStyle(
        "title", fontName="AnexoSans-Bold", fontSize=15, leading=19,
        alignment=TA_CENTER, textColor=NAVY, spaceAfter=4,
    ),
    "subtitle": ParagraphStyle(
        "subtitle", fontName="AnexoSans", fontSize=8.5, leading=11,
        alignment=TA_CENTER, textColor=colors.HexColor("#5b6573"), spaceAfter=10,
    ),
    "h1": ParagraphStyle(
        "h1", fontName="AnexoSans-Bold", fontSize=11.5, leading=14,
        textColor=NAVY, spaceBefore=8, spaceAfter=4, keepWithNext=True,
    ),
    "body": ParagraphStyle(
        "body", fontName="AnexoSans", fontSize=8.5, leading=11.5,
        alignment=TA_JUSTIFY, spaceAfter=4,
    ),
    "cell": ParagraphStyle("cell", fontName="AnexoSans", fontSize=7.2, leading=9),
    "cellmono": ParagraphStyle("cellmono", fontName="AnexoMono", fontSize=6.6, leading=8.5),
    "caption": ParagraphStyle(
        "caption", fontName="AnexoSans", fontSize=7.5, leading=9.5,
        alignment=TA_CENTER, textColor=colors.HexColor("#5b6573"), spaceAfter=8,
    ),
}


# --------------------------------------------------------------------------- #
# Recolección de evidencia
# --------------------------------------------------------------------------- #
NAMESPACE = "pset2.pipeline"
BACKFILL_FLOW = "backfill_report_history"


def _kestra(path: str, params: dict | None = None, raw: bool = False):
    """GET autenticado a la API de Kestra (KESTRA_URL, KESTRA_USER, KESTRA_PASSWORD)."""
    import base64
    import urllib.parse
    import urllib.request

    base = os.environ.get("KESTRA_URL", "http://localhost:8080").rstrip("/")
    url = f"{base}/api/v1/main/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    token = base64.b64encode(
        f"{os.environ['KESTRA_USER']}:{os.environ['KESTRA_PASSWORD']}".encode()
    ).decode()
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
    return body if raw else json.loads(body)


def _iso_duration(value: str | None) -> str:
    """PT2M5.377S -> 00:02:05.377"""
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", value or "")
    if not m:
        return value or "—"
    h, mi, se = (float(g) if g else 0.0 for g in m.groups())
    return f"{int(h):02d}:{int(mi):02d}:{se:06.3f}"


def _executions(flow_id: str) -> list[dict]:
    page = _kestra(
        "executions/search",
        {"namespace": NAMESPACE, "flowId": flow_id, "size": 100, "sort": "state.startDate:desc"},
    )
    # El filtro flowId no siempre se aplica en la API de Kestra 2: se filtra aquí.
    results = [
        e for e in page.get("results", [])
        if e.get("flowId") == flow_id and e.get("namespace") == NAMESPACE
    ]
    return sorted(results, key=lambda e: e["state"]["startDate"], reverse=True)


def _task_types(flow_id: str) -> dict[str, str]:
    flow = _kestra(f"flows/{NAMESPACE}/{flow_id}")
    types: dict[str, str] = {}

    def walk(tasks):
        for task in tasks or []:
            types[task["id"]] = task["type"].rsplit(".", 1)[-1]
            for key in ("tasks", "then", "else", "errors"):
                walk(task.get(key))

    walk(flow.get("tasks"))
    walk(flow.get("errors"))
    return types


def _task_rows(execution: dict, types: dict[str, str]) -> list[dict]:
    """Tareas del flow; omite los nodos de dbt que DbtCLI registra como sub-tareas."""
    return [
        {
            "task": run["taskId"],
            "type": types.get(run["taskId"], "—"),
            "state": run["state"]["current"],
            "duration": _iso_duration(run["state"].get("duration")),
            "attempts": len(run.get("attempts") or []),
        }
        for run in execution.get("taskRunList") or []
        if run["taskId"] in types
    ]


def _logs(execution_id: str, task_id: str, needle: str) -> list[str]:
    logs = _kestra(f"logs/{execution_id}", {"minLevel": "INFO"})
    return [
        line["message"].strip()
        for line in logs
        if line.get("taskId") == task_id and needle in (line.get("message") or "")
    ]


def _execution_summary(execution: dict) -> dict:
    labels = {l["key"]: l["value"] for l in execution.get("labels") or []}
    trigger = execution.get("trigger") or {}
    return {
        "execution_id": execution["id"],
        "state": execution["state"]["current"],
        "started_utc": execution["state"]["startDate"][:19],
        "duration": _iso_duration(execution["state"].get("duration")),
        "trigger": trigger.get("id") or labels.get("system.from", "manual"),
        "inputs": execution.get("inputs") or {},
    }


def _collect_kestra() -> dict:
    types = _task_types(FLOW)
    runs = [_kestra(f"executions/{e['id']}") for e in _executions(FLOW)]

    # 1. Última ejecución completa (ingesta + dbt + Spark) terminada en SUCCESS.
    main = next(
        e for e in runs
        if e["state"]["current"] == "SUCCESS"
        and (e.get("inputs") or {}).get("run_transformations", True)
        and any(t["taskId"] == "spark_obt" for t in e.get("taskRunList") or [])
    )
    dbt_run = next(t for t in main["taskRunList"] if t["taskId"] == "dbt_build")
    commit = _logs(main["id"], "extract_dataset", "-> commit")

    # 2. Último backfill en SUCCESS y las cargas históricas que lanzó.
    backfill = next(
        _kestra(f"executions/{e['id']}") for e in _executions(BACKFILL_FLOW)
        if e["state"]["current"] == "SUCCESS"
    )
    started, ended = backfill["state"]["startDate"], backfill["state"].get("endDate") or "9999"
    loads = []
    for e in runs:
        if started <= e["state"]["startDate"] <= ended:
            loads.append({
                **_execution_summary(e),
                "commit_log": next(iter(_logs(e["id"], "extract_dataset", "-> commit")), ""),
            })
    loads.sort(key=lambda r: str(r["inputs"].get("snapshot_date", "")))

    # 3. Última ejecución fallida en la que corrió el bloque `errors`.
    failed = next(
        e for e in runs
        if e["state"]["current"] == "FAILED"
        and any(t["taskId"] == "cleanup_on_failure" for t in e.get("taskRunList") or [])
    )
    failure_msg = next(iter(_logs(failed["id"], "log_failure", "Falló")), "")
    failed_task = next(t["taskId"] for t in failed["taskRunList"] if t["state"]["current"] == "FAILED")
    cause = next(
        (line.splitlines()[-1] for line in _logs(failed["id"], failed_task, "Error")
         if re.search(r"^\w*Error: ", line.splitlines()[-1])),
        "",
    )

    return {
        "flow": f"{NAMESPACE}.{FLOW}",
        "main": {
            **_execution_summary(main),
            "tasks": _task_rows(main, types),
            "commit_log": next(iter(commit), ""),
            "spark_log": _logs(main["id"], "spark_obt", "[validación]")
            + _logs(main["id"], "spark_obt", "OBT GOLD."),
            "dbt_task_run": dbt_run["id"],
        },
        "backfill": {
            "flow": f"{NAMESPACE}.{BACKFILL_FLOW}",
            **_execution_summary(backfill),
            "tasks": _task_rows(backfill, _task_types(BACKFILL_FLOW)),
            "loads": loads,
        },
        "error_handling": {
            **_execution_summary(failed),
            "tasks": _task_rows(failed, types),
            "log_failure": failure_msg.split(" Detalle:")[0],
            "failed_task": failed_task,
            "cause": cause,
        },
        "source": "API REST de Kestra (/executions, /logs)",
    }


def _collect_dbt(kestra: dict) -> dict:
    """run_results.json que DbtCLI guardó en el storage de Kestra para la ejecución principal."""
    main = kestra["main"]
    uri = (
        f"kestra:///{NAMESPACE.replace('.', '/')}/{FLOW.replace('_', '-')}/executions/"
        f"{main['execution_id']}/tasks/dbt-build/{main['dbt_task_run']}/run_results.json"
    )
    data = json.loads(_kestra(f"executions/{main['execution_id']}/file", {"path": uri}, raw=True))
    results = []
    for item in data["results"]:
        kind, _, name = item["unique_id"].split(".", 2)
        results.append({
            "kind": kind,
            "name": re.sub(r"\.[0-9a-f]{10}$", "", name),
            "status": item["status"],
            "seconds": round(item["execution_time"], 2),
            "rows": (item.get("adapter_response") or {}).get("rows_affected"),
        })
    return {
        "command": f"dbt {data['args'].get('which')}",
        "generated_at": data["metadata"]["generated_at"][:19],
        "elapsed_seconds": round(data["elapsed_time"], 1),
        "dbt_version": data["metadata"].get("dbt_version"),
        "kestra_execution": main["execution_id"],
        "results": results,
    }


def _collect_snowflake() -> dict:
    import snowflake.connector

    db = os.environ["SNOWFLAKE_DATABASE"]
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ.get("SNOWFLAKE_ROLE"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE"),
        database=db,
        login_timeout=60,
    )
    queries = {
        "tablas": f"""SELECT TABLE_SCHEMA, TABLE_NAME, ROW_COUNT,
       TO_CHAR(CONVERT_TIMEZONE('UTC', LAST_ALTERED), 'YYYY-MM-DD HH24:MI') AS ULTIMA_ACTUALIZACION_UTC
FROM {db}.INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA IN ('RAW', 'BRONZE', 'SILVER', 'GOLD') AND ROW_COUNT > 0
  AND TABLE_NAME NOT LIKE 'REPORT_INGEST_LOAD_%'
ORDER BY CASE TABLE_SCHEMA WHEN 'RAW' THEN 1 WHEN 'BRONZE' THEN 2
         WHEN 'SILVER' THEN 3 ELSE 4 END, TABLE_NAME""",
        "particiones_raw": f"""SELECT SNAPSHOT_DATE, LEFT(SOURCE_COMMIT, 7) AS COMMIT_REPORT,
       COUNT(*) AS FILAS, COUNT(DISTINCT EXPERIMENT_ID) AS EXPERIMENTOS,
       TO_CHAR(CONVERT_TIMEZONE('UTC', MAX(INGESTED_AT)), 'YYYY-MM-DD HH24:MI') AS CARGADO_UTC
FROM {db}.RAW.RAW_REPORT_DATA GROUP BY 1, 2 ORDER BY 1""",
        "exclusiones": f"""SELECT COALESCE(MOTIVO_EXCLUSION, '(conservada)') AS MOTIVO,
       COUNT(*) AS FILAS, COUNT(DISTINCT EXPERIMENTO_ID) AS EXPERIMENTOS
FROM {db}.SILVER.INT_REGISTROS_CLASIFICADOS GROUP BY 1 ORDER BY 2 DESC""",
        "obt": f"""SELECT COUNT(*) AS TOTAL_FILAS, COUNT(DISTINCT HECHO_ID) AS HECHOS_UNICOS,
       COUNT_IF(HECHO_ID IS NULL) AS HECHO_ID_NULOS,
       (SELECT COUNT(*) FROM {db}.GOLD.FACT_RETENCION_CROMATOGRAFICA) AS FILAS_HECHO
FROM {db}.GOLD.OBT_QSRR_FINAL""",
        "referencial": f"""SELECT
  (SELECT COUNT(*) FROM {db}.GOLD.FACT_RETENCION_CROMATOGRAFICA f
     LEFT JOIN {db}.GOLD.DIM_COMPUESTO d USING (COMPUESTO_ID)
    WHERE d.COMPUESTO_ID IS NULL) AS HECHOS_SIN_COMPUESTO,
  (SELECT COUNT(*) FROM {db}.GOLD.FACT_RETENCION_CROMATOGRAFICA f
     LEFT JOIN {db}.GOLD.DIM_CONDICIONES d USING (CONDICION_ID)
    WHERE d.CONDICION_ID IS NULL) AS HECHOS_SIN_CONDICION""",
        "muestra_obt": f"""SELECT HECHO_ID, EXPERIMENTO_ID, INCHIKEY, N_MEDICIONES, TIEMPO_RETENCION
FROM {db}.GOLD.OBT_QSRR_FINAL ORDER BY HECHO_ID LIMIT 5""",
    }
    out = {"consultado_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M")}
    try:
        cursor = conn.cursor()
        for name, sql in queries.items():
            cursor.execute(sql)
            out[name] = {
                "sql": sql.replace(f"{db}.", "<DB>."),
                "columns": [d[0] for d in cursor.description],
                "rows": [["—" if v is None else str(v) for v in row] for row in cursor.fetchall()],
            }
    finally:
        conn.close()
    return out


def refresh() -> None:
    EVIDENCE.mkdir(exist_ok=True)
    kestra = _collect_kestra()
    for name, data in (
        ("kestra", kestra),
        ("dbt", _collect_dbt(kestra)),
        ("snowflake", _collect_snowflake()),
    ):
        (EVIDENCE / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Evidencia actualizada: docs/evidencia/{name}.json")


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
def _p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def _table(rows: list[list[str]], widths: list[float], mono_cols: tuple[int, ...] = ()) -> Table:
    body = [
        [
            _p(f"<b>{escape(str(c))}</b>" if r == 0 else escape(str(c)),
               "cellmono" if r > 0 and i in mono_cols else "cell")
            for i, c in enumerate(row)
        ]
        for r, row in enumerate(rows)
    ]
    table = Table(body, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce6f1")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7c4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _sql(sql: str) -> Table:
    lines = "<br/>".join(escape(line).replace(" ", "&nbsp;") for line in sql.splitlines())
    box = Table([[_p(lines, "cellmono")]], hAlign="LEFT")
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f6f8")),
        ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor("#aab7c4")),
    ]))
    return box


def _captures(width: float, max_height: float) -> list:
    files = sorted(
        p for p in CAPTURES.glob("*")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ) if CAPTURES.is_dir() else []
    captions_file = CAPTURES / "pies.json"
    captions = (
        json.loads(captions_file.read_text(encoding="utf-8")) if captions_file.is_file() else {}
    )
    story = []
    for number, path in enumerate(files, start=1):
        image = Image(str(path))
        scale = min(width / image.imageWidth, max_height / image.imageHeight)
        image.drawWidth, image.drawHeight = image.imageWidth * scale, image.imageHeight * scale
        caption = captions.get(path.name) or re.sub(
            r"^\d+[_\- ]*", "", path.stem
        ).replace("_", " ").strip()
        story.append(KeepTogether([
            image,
            _p(f"Figura A{number}. {escape(caption[:1].upper() + caption[1:])}", "caption"),
        ]))
    return story


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("AnexoSans", 7)
    canvas.setFillColor(colors.HexColor("#5b6573"))
    canvas.drawString(18 * mm, 10 * mm, "PSet 2 · Anexos de evidencia")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _int(v: str) -> str:
    try:
        return f"{int(v):,}"
    except ValueError:
        return v


def _task_table(tasks: list[dict], w: float) -> Table:
    return _table(
        [["#", "Tarea", "Tipo", "Estado", "Intentos", "Duración"]]
        + [[str(i), t["task"], t["type"], t["state"], str(t["attempts"]), t["duration"]]
           for i, t in enumerate(tasks, start=1)],
        [w * 0.05, w * 0.33, w * 0.17, w * 0.12, w * 0.11, w * 0.22], mono_cols=(1,),
    )


def _query_block(title: str, block: dict, widths: list[float], fmt=None) -> list:
    rows = [fmt(r) if fmt else r for r in block["rows"]]
    return [
        KeepTogether([
            _p(f"<b>{title}</b>"),
            _sql(block["sql"]),
            Spacer(1, 3),
            _table([block["columns"]] + rows, widths),
        ]),
        Spacer(1, 6),
    ]


def build() -> None:
    kestra = json.loads((EVIDENCE / "kestra.json").read_text(encoding="utf-8"))
    dbt = json.loads((EVIDENCE / "dbt.json").read_text(encoding="utf-8"))
    sf = json.loads((EVIDENCE / "snowflake.json").read_text(encoding="utf-8"))
    main, backfill, err = kestra["main"], kestra["backfill"], kestra["error_handling"]

    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=14 * mm, bottomMargin=16 * mm,
        title="PSet 2 — Anexos de evidencia", author="Jonatan Buenaño",
    )
    w = doc.width
    story = [
        _p("PSet 2 — Anexos de evidencia de ejecución", "title"),
        _p("Pipeline RepoRT → Kestra → Snowflake RAW → dbt (Bronze/Silver/Gold) → Spark → OBT", "subtitle"),
        _p(
            "Este anexo complementa el memo técnico con evidencia de que el pipeline corre de "
            "punta a punta orquestado por Kestra: la ejecución completa (ingesta, <i>dbt build</i> "
            "y Spark), el backfill histórico, el bloque de errores, el resultado de cada modelo y "
            "prueba de dbt y consultas de verificación en Snowflake. Las tablas se generan con "
            "<i>docs/generate_anexos.py --refresh</i> a partir de la API de Kestra, del "
            "<i>run_results.json</i> que Kestra guarda para la tarea dbt y de consultas de solo "
            "lectura; no se transcriben a mano."
        ),
    ]

    captures = _captures(w, doc.height * 0.42)
    if captures:
        story += [_p("A. Capturas de pantalla", "h1")] + captures

    # B. Kestra
    story += [
        _p("B. Orquestación con Kestra", "h1"),
        _p("<b>B.1 Ejecución completa del pipeline</b>"),
        _p(
            f"Flow <b>{escape(kestra['flow'])}</b>, ejecución "
            f"<font name='AnexoMono'>{escape(main['execution_id'])}</font> "
            f"(origen: {escape(main['trigger'])}), iniciada el "
            f"{escape(main['started_utc'].replace('T', ' '))} UTC; estado "
            f"<b>{escape(main['state'])}</b> en {escape(main['duration'])}. La misma ejecución "
            "carga Raw, lanza <i>dbt build</i> y el job Spark en contenedores. Commit cargado: "
            f"<font name='AnexoMono'>{escape(main['commit_log'])}</font>."
        ),
        _task_table(main["tasks"], w),
        Spacer(1, 6),
        _p(
            "<b>B.2 Validaciones de Spark antes de escribir la OBT</b> (log de la tarea "
            "<i>spark_obt</i>). Si alguna falla, el job termina con código 1 sin escribir."
        ),
        _sql("\n".join(main["spark_log"])),
        Spacer(1, 6),
        _p("<b>B.3 Backfill histórico</b>"),
        _p(
            f"Flow <b>{escape(backfill['flow'])}</b>, ejecución "
            f"<font name='AnexoMono'>{escape(backfill['execution_id'])}</font>: "
            f"<b>{escape(backfill['state'])}</b> en {escape(backfill['duration'])} con "
            f"start_date={escape(str(backfill['inputs'].get('start_date')))}, "
            f"end_date={escape(str(backfill['inputs'].get('end_date')))}, "
            f"step={escape(str(backfill['inputs'].get('step')))}. Cada fecha se cargó como "
            "subflow con el commit de RepoRT vigente ese día, en su propia partición de Raw "
            "(ver D.2):"
        ),
        _table(
            [["snapshot_date", "Ejecución", "Estado", "Duración", "Commit resuelto"]]
            + [[str(l["inputs"].get("snapshot_date")), l["execution_id"], l["state"],
                l["duration"], l["commit_log"].split("-> commit ")[-1]]
               for l in backfill["loads"]],
            [w * 0.14, w * 0.26, w * 0.11, w * 0.14, w * 0.35], mono_cols=(1, 4),
        ),
        Spacer(1, 6),
        KeepTogether([
            _p("<b>B.4 Bloque de errores</b>"),
            _p(
                f"Ejecución <font name='AnexoMono'>{escape(err['execution_id'])}</font> "
                f"({escape(err['started_utc'].replace('T', ' '))} UTC): la tarea "
                f"<i>{escape(err.get('failed_task', ''))}</i> falló tras agotar sus reintentos "
                "(cambio de esquema en un commit antiguo de RepoRT, corregido después). Kestra "
                "ejecutó entonces el bloque <i>errors</i>: <i>log_failure</i> registró el fallo y "
                "<i>cleanup_on_failure</i> borró la tabla transient y los archivos del stage. "
                "Causa y mensaje registrados:"
            ),
            _sql(err.get("cause", "") + "\n" + err["log_failure"]),
            Spacer(1, 3),
            _task_table(err["tasks"], w),
        ]),
        PageBreak(),
    ]

    # C. dbt
    counts = {}
    for r in dbt["results"]:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    summary = ", ".join(f"{v} {k.upper()}" for k, v in counts.items())
    story += [
        _p("C. Transformaciones con dbt", "h1"),
        _p(
            f"Resultado de <b>{escape(dbt['command'])}</b> (dbt {escape(str(dbt['dbt_version']))}) "
            f"ejecutado por Kestra en la ejecución "
            f"<font name='AnexoMono'>{escape(dbt['kestra_execution'])}</font> el "
            f"{escape(dbt['generated_at'].replace('T', ' '))} UTC, en {dbt['elapsed_seconds']} s: "
            f"<b>{len(dbt['results'])} acciones, {summary}</b>. Además de <i>not_null</i>, "
            "<i>unique</i> y <i>relationships</i>, incluye pruebas de dominio (<i>en_rango</i>, "
            "RT &gt; t0, motivos de exclusión válidos) y de conservación de filas entre capas "
            "(<i>assert_*</i>)."
        ),
        _table(
            [["Tipo", "Modelo / prueba", "Estado", "Filas", "Seg."]]
            + [["modelo" if r["kind"] == "model" else "prueba",
                r["name"].removeprefix("pset_02_qsrr."), r["status"].upper(),
                f"{r['rows']:,}" if r["kind"] == "model" and r["rows"] is not None else "—",
                f"{r['seconds']:.2f}"] for r in dbt["results"]],
            [w * 0.10, w * 0.62, w * 0.10, w * 0.10, w * 0.08], mono_cols=(1,),
        ),
        _p("Fuente: run_results.json de la tarea dbt_build en el storage de Kestra.", "caption"),
    ]

    # D. Snowflake
    tablas = sf["tablas"]
    story += [
        _p("D. Verificación en Snowflake", "h1"),
        _p(
            f"Consultas de solo lectura ejecutadas el {escape(sf['consultado_utc'])} UTC. "
            "Los conteos coinciden con los del memo."
        ),
        _p("<b>D.1 Tablas por capa</b>"),
        _sql(tablas["sql"]),
        Spacer(1, 3),
        _table(
            [["Esquema", "Tabla", "Filas", "Última actualización (UTC)"]]
            + [[r[0], r[1], _int(r[2]), r[3]] for r in tablas["rows"]],
            [w * 0.14, w * 0.44, w * 0.14, w * 0.28], mono_cols=(1,),
        ),
        _p(
            "RAW_REPORT_DATA suma todas las particiones de snapshot; Bronze toma solo la más "
            "reciente.", "caption",
        ),
    ]
    story += _query_block(
        "D.2 Particiones de Raw (snapshot actual y backfill)", sf["particiones_raw"],
        [w * 0.18, w * 0.20, w * 0.16, w * 0.18, w * 0.28],
        lambda r: [r[0], r[1], _int(r[2]), _int(r[3]), r[4]],
    )
    story += _query_block(
        "D.3 Decisiones de limpieza en Silver", sf["exclusiones"],
        [w * 0.56, w * 0.22, w * 0.22], lambda r: [r[0], _int(r[1]), _int(r[2])],
    )
    story += _query_block(
        "D.4 Grano de la OBT escrita por Spark", sf["obt"], [w / 4] * 4,
        lambda r: [_int(v) for v in r],
    )
    story += _query_block(
        "D.5 Integridad referencial en Gold", sf["referencial"], [w / 2] * 2,
        lambda r: [_int(v) for v in r],
    )
    sample = sf["muestra_obt"]
    story += [
        KeepTogether([
            _p("<b>D.6 Muestra de la OBT final</b>"),
            _sql(sample["sql"]),
            Spacer(1, 3),
            _table([sample["columns"]]
                   + [row[:-1] + [f"{float(row[-1]):.3f}"] for row in sample["rows"]],
                   [w * 0.30, w * 0.15, w * 0.29, w * 0.13, w * 0.13], mono_cols=(0, 2)),
        ]),
    ]

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"PDF generado: {OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="recolecta evidencia nueva")
    if parser.parse_args().refresh:
        refresh()
    build()
