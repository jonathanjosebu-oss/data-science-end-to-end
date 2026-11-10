"""Download RepoRT's canonical successful retention-time tables as one CSV."""

import argparse
import csv
import io
import sys
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


REPOSITORY = "michaelwitting/RepoRT"
API_ROOT = f"https://api.github.com/repos/{REPOSITORY}"
RAW_ROOT = f"https://raw.githubusercontent.com/{REPOSITORY}"
THREAD_LOCAL = threading.local()

OUTPUT_COLUMNS = [
    "experiment_id",
    "id",
    "name",
    "formula",
    "rt",
    "smiles_std",
    "inchi_std",
    "inchikey_std",
    "classyfire_kingdom",
    "classyfire_superclass",
    "classyfire_class",
    "classyfire_subclass",
    "classyfire_level5",
    "classyfire_level6",
    "comment",
    "column_name",
    "column_usp_code",
    "column_length",
    "column_id",
    "column_particle_size",
    "column_temperature",
    "column_flowrate",
    "column_t0",
    "eluent_a_h2o",
    "eluent_a_meoh",
    "eluent_a_acn",
    "eluent_b_h2o",
    "eluent_b_meoh",
    "eluent_b_acn",
]

MEASUREMENT_FIELDS = {
    "id": "id",
    "name": "name",
    "formula": "formula",
    "rt": "rt",
    "smiles.std": "smiles_std",
    "inchi.std": "inchi_std",
    "inchikey.std": "inchikey_std",
    "classyfire.kingdom": "classyfire_kingdom",
    "classyfire.superclass": "classyfire_superclass",
    "classyfire.class": "classyfire_class",
    "classyfire.subclass": "classyfire_subclass",
    "classyfire.level5": "classyfire_level5",
    "classyfire.level6": "classyfire_level6",
    "comment": "comment",
}

METADATA_FIELDS = {
    "column.name": "column_name",
    "column.usp.code": "column_usp_code",
    "column.length": "column_length",
    "column.id": "column_id",
    "column.particle.size": "column_particle_size",
    "column.temperature": "column_temperature",
    "column.flowrate": "column_flowrate",
    "column.t0": "column_t0",
    "eluent.A.h2o": "eluent_a_h2o",
    "eluent.A.meoh": "eluent_a_meoh",
    "eluent.A.acn": "eluent_a_acn",
    "eluent.B.h2o": "eluent_b_h2o",
    "eluent.B.meoh": "eluent_b_meoh",
    "eluent.B.acn": "eluent_b_acn",
}


def session() -> requests.Session:
    if not hasattr(THREAD_LOCAL, "session"):
        retry = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        client = requests.Session()
        client.mount("https://", adapter)
        THREAD_LOCAL.session = client
    return THREAD_LOCAL.session


def get_text(url: str) -> str:
    response = session().get(url, timeout=(15, 120))
    response.raise_for_status()
    return response.text


def parse_tsv(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def load_experiment(ref: str, data_path: str) -> tuple[str, list[dict[str, str]], dict[str, str]]:
    experiment_id = data_path.split("/")[1]
    metadata_path = f"processed_data/{experiment_id}/{experiment_id}_metadata.tsv"
    encoded_ref = quote(ref, safe="")
    data_url = f"{RAW_ROOT}/{encoded_ref}/{data_path}"
    metadata_url = f"{RAW_ROOT}/{encoded_ref}/{metadata_path}"

    data_text = get_text(data_url)
    metadata_text = get_text(metadata_url)
    measurements = parse_tsv(data_text)
    metadata_rows = parse_tsv(metadata_text)
    if not measurements:
        raise ValueError(f"{data_path} contiene solo el encabezado o está vacío")
    if len(metadata_rows) != 1:
        raise ValueError(
            f"{metadata_path} debe tener una fila de metadata; "
            f"se encontraron {len(metadata_rows)}"
        )
    return experiment_id, measurements, metadata_rows[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_ref", help="Rama o commit de RepoRT")
    parser.add_argument("output_path", help="Ruta del CSV generado")
    parser.add_argument(
        "--max-experiments",
        type=int,
        default=0,
        help="Limita la descarga para una prueba local; 0 descarga todos",
    )
    args = parser.parse_args()

    tree_url = f"{API_ROOT}/git/trees/{quote(args.source_ref, safe='')}?recursive=1"
    tree = session().get(tree_url, timeout=(15, 60))
    tree.raise_for_status()
    data_paths = sorted(
        entry["path"]
        for entry in tree.json().get("tree", [])
        if entry.get("type") == "blob"
        and entry["path"].startswith("processed_data/")
        and entry["path"].endswith("_rtdata_canonical_success.tsv")
    )
    if not data_paths:
        raise RuntimeError(
            f"No se encontraron archivos _rtdata_canonical_success.tsv "
            f"en RepoRT ref '{args.source_ref}'"
        )
    if args.max_experiments > 0:
        data_paths = data_paths[: args.max_experiments]

    executor = ThreadPoolExecutor(max_workers=8)
    pending = {}
    paths = iter(data_paths)
    with open(args.output_path, "w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        try:
            for _ in range(8):
                path = next(paths, None)
                if path is not None:
                    pending[executor.submit(load_experiment, args.source_ref, path)] = path

            row_count = 0
            while pending:
                finished, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    path = pending.pop(future)
                    experiment_id, measurements, metadata = future.result()
                    required_measurements = set(MEASUREMENT_FIELDS) - {"comment"}
                    missing_measurements = required_measurements - measurements[0].keys()
                    missing_metadata = set(METADATA_FIELDS) - metadata.keys()
                    if missing_measurements or missing_metadata:
                        raise ValueError(
                            f"Esquema inesperado en {path}: "
                            f"faltan campos de medición {sorted(missing_measurements)} "
                            f"o metadata {sorted(missing_metadata)}"
                        )

                    for measurement in measurements:
                        row = {"experiment_id": experiment_id}
                        row.update(
                            {
                                output_name: measurement[source_name]
                                for source_name, output_name in MEASUREMENT_FIELDS.items()
                                if source_name in measurement
                            }
                        )
                        row.setdefault("comment", "")
                        row.update(
                            {
                                output_name: metadata[source_name]
                                for source_name, output_name in METADATA_FIELDS.items()
                            }
                        )
                        writer.writerow(row)
                        row_count += 1

                    next_path = next(paths, None)
                    if next_path is not None:
                        pending[
                            executor.submit(load_experiment, args.source_ref, next_path)
                        ] = next_path
        except Exception:
            for future in pending:
                future.cancel()
            raise
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

    if row_count == 0:
        raise RuntimeError("La descarga terminó sin registros")
    print(
        f"RepoRT ref={args.source_ref}: "
        f"{len(data_paths)} experimentos, {row_count} registros, "
        f"archivo={args.output_path}"
    )


if __name__ == "__main__":
    main()
