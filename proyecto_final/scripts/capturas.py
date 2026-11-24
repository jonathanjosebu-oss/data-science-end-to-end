"""Capturas de evidencia para el documento técnico (docs/capturas/).

    python -m scripts.capturas      # requiere la infraestructura arriba, playwright y Chrome

Las capturas de GitHub Actions y GHCR se toman a mano desde GitHub (no hay
acceso a la cuenta desde aquí).
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "capturas"
load_dotenv(RAIZ / ".env")
KESTRA, MLFLOW, API, TABLERO = "http://localhost:8080", "http://localhost:5000", "http://localhost:8000", "http://localhost:8501"
NS = "qsrr.proyecto"
EJECUCIONES = {  # ejecuciones de la simulación final (ver notebooks/06)
    "ingesta": "45WxRvkfRCkSIP8Fjpseow",
    "produccion_lotes": "3aTAQL0NVxgSPBR3r0cFDx",
    "monitoreo_semana8": "RxqtCzeUQX7CL49FjM7PC",
    "reentrenamiento_rechazado": "1Cccteyih5CajW8NsdEgKL",
    "reentrenamiento_aprobado": "gRpmhQCt0Gw3AkZ1o5DyG",
}
SOLICITUD = {
    "tipo_columna": "Waters ACQUITY UPLC BEH C18",
    "fase_movil": "A[H2O=100; MeOH=0; ACN=0] B[H2O=0; MeOH=0; ACN=100]",
    "flujo_ml_min": 0.4, "t0_min": 0.5, "columna_longitud_mm": 100, "columna_diametro_mm": 2.1,
    "columna_particula_um": 1.7, "ph_a": 2.7, "ph_b": 2.7,
    "gradiente": [{"t_min": 0, "a_pct": 95, "b_pct": 5}, {"t_min": 10, "a_pct": 5, "b_pct": 95}],
    "compuestos": [{"id": "cafeina", "smiles": "Cn1cnc2c1c(=O)n(C)c(=O)n2C"},
                   {"id": "ibuprofeno", "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O"}],
}


def foto(pg: Page, nombre: str, espera: int = 3500, completa: bool = False) -> None:
    pg.wait_for_timeout(espera)
    pg.screenshot(path=str(SALIDA / f"{nombre}.png"), full_page=completa)
    print("captura", nombre)


def kestra(pg: Page) -> None:
    pg.goto(f"{KESTRA}/ui/login")
    pg.fill('input[name="username"]', os.environ["KESTRA_USER"])
    pg.fill('input[name="password"]', os.environ["KESTRA_PASSWORD"])
    pg.keyboard.press("Enter")
    pg.wait_for_url("**/ui/main/**", timeout=30_000)
    pg.goto(f"{KESTRA}/ui/main/flows?namespace={NS}")
    foto(pg, "kestra_01_flujos")  # el filtro por namespace se aplica en la URL
    vistas = [
        ("ingesta", "gantt", "kestra_02_ingesta_hasta_obt"),
        ("produccion_lotes", "gantt", "kestra_03_produccion_lotes"),
        ("monitoreo_semana8", "logs", "kestra_04_alerta_monitoreo_semana8"),
        ("reentrenamiento_rechazado", "logs", "kestra_05_reentrenamiento_rechazado"),
        ("reentrenamiento_aprobado", "topology", "kestra_06_reentrenamiento_topologia"),
        ("reentrenamiento_aprobado", "overview", "kestra_07_reentrenamiento_aprobado"),
    ]
    for clave, pestana, nombre in vistas:
        flujo = clave.split("_semana")[0].replace("_rechazado", "").replace("_aprobado", "")
        pg.goto(f"{KESTRA}/ui/main/executions/{NS}/{flujo}/{EJECUCIONES[clave]}/{pestana}")
        pg.wait_for_timeout(5000)
        if clave.startswith("reentrenamiento") and pestana == "logs":
            # La comparación champion/challenger (los ERROR de arriba son avisos de git en stderr).
            pg.get_by_text("RMSE lote", exact=False).first.scroll_into_view_if_needed()
        foto(pg, nombre, espera=1000)
    pg.goto(f"{KESTRA}/ui/main/executions/{NS}/reentrenamiento/{EJECUCIONES['reentrenamiento_aprobado']}/logs")
    pg.wait_for_timeout(5000)
    pg.get_by_text("RMSE lote", exact=False).first.scroll_into_view_if_needed()
    foto(pg, "kestra_08_reentrenamiento_aprobado_comparacion", espera=1000)


def mlflow_ui(pg: Page) -> None:
    pg.goto(f"{MLFLOW}/#/models/qsrr-predict-modelo")
    pg.wait_for_timeout(4000)
    pg.keyboard.press("Escape")  # aviso emergente de la nueva interfaz del registro
    foto(pg, "mlflow_01_registro_aliases", espera=1500)
    exp = requests.get(f"{MLFLOW}/api/2.0/mlflow/experiments/get-by-name",
                       params={"experiment_name": "qsrr-predict-c18"}, timeout=10).json()["experiment"]["experiment_id"]
    pg.goto(f"{MLFLOW}/#/experiments/{exp}")
    foto(pg, "mlflow_02_corridas", espera=5000)


def api(pg: Page) -> None:
    pg.goto(f"{API}/docs")
    foto(pg, "api_01_endpoints")
    ok = requests.post(f"{API}/predecir", json=SOLICITUD, timeout=60)
    malo = {**SOLICITUD, "fase_movil": "agua y alcohol"}
    malo.pop("tipo_columna")
    error = requests.post(f"{API}/predecir", json=malo, timeout=60)
    modelo = requests.get(f"{API}/modelo", timeout=10)
    bloques = [("GET /modelo", modelo), ("POST /predecir (entrada válida)", ok),
               ("POST /predecir (falta tipo_columna y fase_movil inválida)", error)]
    cuerpo = "".join(
        f"<h2>{html.escape(t)} → HTTP {r.status_code}</h2><pre>{html.escape(json.dumps(r.json(), ensure_ascii=False, indent=2)[:2600])}</pre>"
        for t, r in bloques)
    pagina = SALIDA / "_api.html"
    pagina.write_text(f"""<html><head><meta charset="utf-8"><style>
body{{font-family:'Times New Roman',serif;margin:24px;background:#fff}} h2{{color:#c62828;font-size:18px;margin:14px 0 4px}}
pre{{background:#f6f5f2;border:1px solid #ddd;padding:10px;font-size:12px;white-space:pre-wrap}}</style></head>
<body><h1 style="color:#c62828;font-size:22px">Respuestas reales de la API (localhost:8000)</h1>{cuerpo}</body></html>""", encoding="utf-8")
    pg.goto(pagina.as_uri())
    foto(pg, "api_02_respuestas", espera=500, completa=True)
    pagina.unlink()


def tablero(pg: Page) -> None:
    pg.goto(TABLERO)
    pg.wait_for_selector("canvas, svg.marks", timeout=90_000)
    pestanas = pg.locator('button[role="tab"]')
    nombres = ["sistema", "modelo", "desempeno_negocio", "deriva", "alertas"]
    for i, nombre in enumerate(nombres):
        pestanas.nth(i).click()
        foto(pg, f"tablero_0{i + 1}_{nombre}", completa=True)


if __name__ == "__main__":
    SALIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        pg = b.new_page(viewport={"width": 1500, "height": 900})
        for paso in (kestra, mlflow_ui, api, tablero):
            try:
                paso(pg)
            except Exception as exc:  # noqa: BLE001 - seguir con las demás capturas
                print(f"{paso.__name__}: falló ({exc})")
        b.close()
