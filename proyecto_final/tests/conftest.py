"""Configuración común: la API usa la copia del modelo en tests/fixtures/.

En CI no hay servidor de MLflow; el champion se exportó con
mlflow.sklearn.save_model (scripts/registrar_champion.py).
Las variables se fijan antes de importar api.main.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"

os.environ.setdefault("MODELO_URI", str(FIXTURES / "modelo"))
os.environ.setdefault("MODELO_METADATA", str(FIXTURES / "modelo_metadata.json"))
os.environ.setdefault("LINEA_BASE_PATH", str(FIXTURES / "linea_base.json"))
os.environ.setdefault("REGISTROS_DIR", tempfile.mkdtemp(prefix="qsrr_registros_"))
os.environ.setdefault("ADMIN_TOKEN", "token-de-prueba")

COLUMNA = "Waters ACQUITY UPLC BEH C18"
FASE_ACN = "A[H2O=100; MeOH=0; ACN=0] B[H2O=0; MeOH=0; ACN=100]"


@pytest.fixture(scope="session")
def cliente():
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture()
def solicitud_valida() -> dict:
    return {
        "tipo_columna": COLUMNA,
        "fase_movil": FASE_ACN,
        "flujo_ml_min": 0.4,
        "compuestos": [
            {"id": "cafeina", "smiles": "Cn1cnc2c1c(=O)n(C)c(=O)n2C"},
            {"id": "ibuprofeno", "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O"},
            {"id": "tolueno", "smiles": "Cc1ccccc1"},
        ],
    }


@pytest.fixture(scope="session")
def metadata_modelo() -> dict:
    return json.loads((FIXTURES / "modelo_metadata.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def muestra_fija() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "muestra_fija.csv", dtype={"hecho_id": str, "experimento_id": str})


@pytest.fixture(scope="session")
def modelo():
    import mlflow.sklearn

    return mlflow.sklearn.load_model(str(FIXTURES / "modelo"))
