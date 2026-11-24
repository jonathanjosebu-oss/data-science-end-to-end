"""Tareas de la simulación de producción (las ejecuta kestra/produccion_lotes.yml).

    python -m src.produccion preparar          # lotes -> Snowflake (una vez)
    python -m src.produccion predecir --lote 3 # llama a la API y registra
    python -m src.produccion llegada --lote 3  # llegan los targets del lote 2

El patrón es online: cada método del lote es una solicitud a la API, como la
haría el analista; la simulación solo reproduce ese tráfico semana a semana.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone

import pandas as pd
import requests

from src import almacen
from src.simulacion import HORIZONTE_LOTES, construir_lotes, solicitudes_de_lote

API_URL = os.getenv("API_URL", "http://api:8000")


def _kestra_outputs(**valores) -> None:
    print("::" + json.dumps({"outputs": valores}, default=str) + "::")


def preparar() -> None:
    """Construye los 10 lotes desde la OBT (split por experimento) y los sube."""
    from src.datos import load_snapshot
    from src.splits import create_or_load_lots

    almacen.asegurar_tablas()
    frame, metadata = load_snapshot()
    frame, lotes = create_or_load_lots(frame, source_sha256=metadata["sha256"])
    entradas, targets = construir_lotes(frame)
    n_e = almacen.escribir("LOTES_ENTRADAS", entradas, borrar_donde="TRUE")
    n_t = almacen.escribir("LAB_MEDICIONES", targets, borrar_donde="TRUE")
    for tabla in ("TARGETS", "PREDICCIONES", "SOLICITUDES", "MONITOREO", "ALERTAS", "REENTRENAMIENTOS"):
        almacen.ejecutar(f"DELETE FROM {tabla}")
    print(f"Lotes preparados: {n_e} entradas, {n_t} mediciones de laboratorio (aún ocultas)")
    _kestra_outputs(entradas=n_e, lotes=int(entradas["lote"].nunique()), corte=lotes["cutoff_experiment"])


def predecir(lote: int) -> None:
    """Envía cada método del lote a la API y registra predicciones y solicitudes."""
    entradas = almacen.consultar("SELECT * FROM LOTES_ENTRADAS WHERE LOTE = %s", (lote,))
    if entradas.empty:
        raise ValueError(f"El lote {lote} no existe en LOTES_ENTRADAS")
    predicciones, solicitudes = [], []
    sesion = requests.Session()
    for solicitud in solicitudes_de_lote(entradas):
        inicio = time.perf_counter()
        ts = datetime.now(timezone.utc)
        try:
            respuesta = sesion.post(f"{API_URL}/predecir", json=solicitud, timeout=60)
            status = respuesta.status_code
            cuerpo = respuesta.json()
        except requests.RequestException as exc:
            status, cuerpo = 599, {"mensaje": str(exc)}
        latencia = (time.perf_counter() - inicio) * 1000
        experimento = entradas.loc[
            entradas["hecho_id"] == solicitud["compuestos"][0]["id"], "experimento_id"
        ].iloc[0]
        id_solicitud = cuerpo.get("id_solicitud") or str(uuid.uuid4())
        solicitudes.append(
            {
                "id_solicitud": id_solicitud, "ts": ts, "lote": lote, "experimento_id": experimento,
                "n_compuestos": len(solicitud["compuestos"]), "status": status,
                "latencia_ms": latencia, "error": None if status == 200 else cuerpo.get("mensaje", "")[:500],
            }
        )
        if status != 200:
            continue
        metodo = {k: v for k, v in solicitud.items() if k not in ("compuestos", "lote")}
        smiles = {c["id"]: c["smiles"] for c in solicitud["compuestos"]}
        for p in cuerpo["predicciones"]:
            predicciones.append(
                {
                    "id_prediccion": p["id_prediccion"], "id_solicitud": id_solicitud, "ts": ts,
                    "lote": lote, "hecho_id": p["id"], "experimento_id": experimento,
                    "smiles": smiles[p["id"]], "tipo_columna": solicitud["tipo_columna"],
                    "fase_movil": solicitud["fase_movil"], "flujo_ml_min": solicitud["flujo_ml_min"],
                    "entrada_metodo": json.dumps(metodo), "prediccion_min": p["tiempo_retencion_min"],
                    "decision": cuerpo["decision"], "fuera_de_dominio": cuerpo["fuera_de_dominio"],
                    "respaldo_usado": cuerpo["respaldo_usado"], "modelo": cuerpo["modelo"],
                    "version_modelo": cuerpo["version_modelo"], "alias": cuerpo["alias"],
                    "run_id": cuerpo["run_id"], "latencia_ms": cuerpo["latencia_ms"],
                    "advertencias": "|".join(cuerpo["advertencias"]),
                }
            )
    n_p = almacen.escribir("PREDICCIONES", pd.DataFrame(predicciones), borrar_donde=f"LOTE = {lote}")
    n_s = almacen.escribir("SOLICITUDES", pd.DataFrame(solicitudes), borrar_donde=f"LOTE = {lote}")
    errores = sum(s["status"] != 200 for s in solicitudes)
    versiones = sorted({p["version_modelo"] for p in predicciones if p["version_modelo"] is not None})
    print(f"Lote {lote}: {n_s} solicitudes ({errores} con error), {n_p} predicciones, versiones {versiones}")
    _kestra_outputs(lote=lote, solicitudes=n_s, errores=errores, predicciones=n_p, versiones=versiones)


def llegada(lote: int) -> None:
    """En la semana del lote k llegan las mediciones del lote k - horizonte."""
    origen = lote - HORIZONTE_LOTES
    if origen < 1:
        print(f"Semana {lote}: todavía no llega ningún target (horizonte {HORIZONTE_LOTES} lote)")
        _kestra_outputs(lote_con_target=0)
        return
    medidas = almacen.consultar(
        "SELECT LOTE, HECHO_ID, TIEMPO_RETENCION, DERIVA_INDUCIDA FROM LAB_MEDICIONES WHERE LOTE = %s",
        (origen,),
    )
    medidas["llego_en_lote"] = lote
    medidas["cargado_en"] = datetime.now(timezone.utc)
    n = almacen.escribir("TARGETS", medidas, borrar_donde=f"LOTE = {origen}")
    print(f"Semana {lote}: llegaron {n} tiempos medidos del lote {origen}")
    _kestra_outputs(lote_con_target=origen, targets=n)


def semana(numero: int, n_lotes: int = 10) -> None:
    """Una semana de producción: predice el lote k (si existe) y recibe los
    targets del lote k-1. La semana 11 solo recibe los del lote 10."""
    if numero <= n_lotes:
        predecir(numero)
    llegada(numero)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="accion", required=True)
    sub.add_parser("preparar")
    for nombre in ("predecir", "llegada"):
        sub.add_parser(nombre).add_argument("--lote", type=int, required=True)
    sub.add_parser("semana").add_argument("--semana", type=int, required=True)
    args = parser.parse_args()
    if args.accion == "preparar":
        preparar()
    elif args.accion == "semana":
        semana(args.semana)
    else:
        globals()[args.accion](args.lote)


if __name__ == "__main__":
    main()
