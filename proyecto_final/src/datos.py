"""Load and snapshot the PSet 2 Gold OBT joined to RepoRT molecular SMILES."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import snowflake.connector
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
SNAPSHOT_PATH = DATA_DIR / "qsrr_c18.parquet"
METADATA_PATH = DATA_DIR / "qsrr_c18.metadata.json"
REQUIRED_ENV = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
)


def load_local_environment() -> None:
    """Load credentials from the project .env; non-empty values override the shell."""
    for path in (PROJECT_ROOT / ".env",):
        if path.is_file():
            for name, value in dotenv_values(path).items():
                if value:
                    os.environ[name] = value


def _database_name() -> str:
    name = os.environ.get("SNOWFLAKE_DATABASE", "")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", name):
        raise ValueError("SNOWFLAKE_DATABASE must be a valid Snowflake identifier")
    return name.upper()


def _connection_settings() -> dict[str, str]:
    load_local_environment()
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Missing required Snowflake environment variables: "
            + ", ".join(missing)
        )
    return {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "password": os.environ["SNOWFLAKE_PASSWORD"],
        "role": os.environ["SNOWFLAKE_ROLE"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": _database_name(),
    }


def _query(database: str) -> str:
    return f"""
        WITH smiles_by_compound AS (
            SELECT
                UPPER(TRIM(INCHIKEY_STD)) AS INCHIKEY,
                NULLIF(TRIM(SMILES_STD), '') AS SMILES
            FROM {database}.RAW.RAW_REPORT_DATA
            -- RAW keeps one partition per snapshot (backfill); use the one
            -- that Bronze/Gold were built from: the most recent.
            WHERE SNAPSHOT_DATE = (
                SELECT MAX(SNAPSHOT_DATE) FROM {database}.RAW.RAW_REPORT_DATA
            )
              AND INCHIKEY_STD IS NOT NULL
              AND SMILES_STD IS NOT NULL
              AND TRIM(SMILES_STD) <> ''
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY UPPER(TRIM(INCHIKEY_STD))
                ORDER BY EXPERIMENT_ID, ID
            ) = 1
        )
        SELECT
            o.HECHO_ID,
            UPPER(TRIM(o.INCHIKEY)) AS INCHIKEY,
            o.NOMBRE_COMPUESTO,
            o.TIPO_COLUMNA,
            o.FASE_MOVIL,
            TRY_TO_DOUBLE(o.FLUJO_ML_MIN) AS FLUJO_ML_MIN,
            TRY_TO_DOUBLE(o.TIEMPO_RETENCION) AS TIEMPO_RETENCION,
            s.SMILES
        FROM {database}.GOLD.OBT_QSRR_FINAL AS o
        LEFT JOIN smiles_by_compound AS s
            ON UPPER(TRIM(o.INCHIKEY)) = s.INCHIKEY
        WHERE UPPER(COALESCE(o.TIPO_COLUMNA, '')) LIKE '%C18%'
          AND TRY_TO_DOUBLE(o.TIEMPO_RETENCION) > 0
    """


def canonical_data_hash(frame: pd.DataFrame) -> str:
    if "hecho_id" not in frame:
        raise ValueError("The dataset must include the hecho_id column")
    canonical = frame.sort_values("hecho_id", kind="mergesort").to_csv(
        index=False,
        na_rep="<NA>",
        float_format="%.12g",
        lineterminator="\n",
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fetch_c18_data() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fetch a C18-only PSet 2 snapshot and return its provenance metadata."""
    settings = _connection_settings()
    connection = snowflake.connector.connect(
        account=settings["account"],
        user=settings["user"],
        password=settings["password"],
        role=settings["role"],
        warehouse=settings["warehouse"],
        database=settings["database"],
        schema="GOLD",
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(_query(settings["database"]))
            frame = cursor.fetch_pandas_all()
    finally:
        connection.close()

    if frame is None or frame.empty:
        raise ValueError(
            "The PSet 2 OBT query returned no C18 observations; "
            "check the Snowflake objects and column naming."
        )

    frame.columns = [column.lower() for column in frame.columns]
    frame["hecho_id"] = frame["hecho_id"].astype("string")
    frame["inchikey"] = frame["inchikey"].astype("string")
    frame["tiempo_retencion"] = pd.to_numeric(
        frame["tiempo_retencion"], errors="coerce"
    )
    frame["flujo_ml_min"] = pd.to_numeric(frame["flujo_ml_min"], errors="coerce")
    loaded_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "source_tables": (
            f"{settings['database']}.GOLD.OBT_QSRR_FINAL,"
            f"{settings['database']}.RAW.RAW_REPORT_DATA"
        ),
        "scope": "RepoRT C18; positive retention-time observations",
        "snapshot_read_at_utc": loaded_at,
        "source_ref": os.getenv("REPORRT_SOURCE_REF", "not-recorded"),
        "sha256": canonical_data_hash(frame),
        "rows": int(len(frame)),
    }
    return frame, metadata


def load_snapshot(force_refresh: bool = False) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Reuse the local immutable snapshot, or fetch and persist a new one."""
    if not force_refresh and SNAPSHOT_PATH.is_file() and METADATA_PATH.is_file():
        frame = pd.read_parquet(SNAPSHOT_PATH)
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        actual_hash = canonical_data_hash(frame)
        if actual_hash != metadata.get("sha256"):
            raise ValueError(
                "The local dataset snapshot hash does not match its metadata; "
                "refresh it explicitly before training."
            )
        return frame, metadata

    frame, metadata = fetch_c18_data()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(SNAPSHOT_PATH, index=False)
    METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return frame, metadata
