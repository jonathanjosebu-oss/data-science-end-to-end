"""Monitoreo por semana, alertas y disparador de reentrenamiento (PSet 4 §6-7).

    python -m monitoreo.alertas --semana 7

En la semana k se monitorea el lote k (sistema, modelo, datos, deriva) y el
lote k-1, cuyo target acaba de llegar (desempeño técnico y de negocio).
Escribe PRODUCCION.MONITOREO y PRODUCCION.ALERTAS y devuelve a Kestra si hay
que reentrenar y por qué.

Plantilla de alertas (umbrales en monitoreo/referencia.json, ver deriva.py):

| Alerta | Métrica | Umbral | Ventana | Severidad | Recibe | Acción |
|---|---|---|---|---|---|---|
| desempeno_rmse | RMSE del lote | > p95 pseudo-lotes | 1 lote | Alta | Ciencia de datos | Diagnosticar; 2 lotes seguidos -> reentrenar |
| desempeno_sesgo | |error medio| | > p95 pseudo-lotes | 1 lote | Alta | Ciencia de datos + laboratorio | Revisar equipo/método (retardo, temperatura); 2 lotes -> reentrenar |
| deriva_datos | n features moleculares con PSI > p99 | >= 2 (KS p < 0,01 de respaldo) | 1 lote | Media | Equipo de datos | Revisar fuente; NO reentrenar si el desempeño se mantiene |
| fuera_de_dominio | fracción de filas fuera de rango | > 20 % | 1 lote | Alta | Analistas + ciencia de datos | Confirmar con corrida exploratoria; incorporar métodos al reentrenar |
| categoria_no_vista | fracción con columna/fase no vista | > 50 % | 1 lote | Baja | Equipo de datos | Informativa: ampliar catálogo |
| latencia_p95 | p95 de latencia | > 500 ms | 1 lote | Media | Plataforma | Escalar el servicio |
| errores_4xx | tasa 4xx | > 5 % | 1 lote | Media | Equipo de datos | Revisar calidad de las solicitudes |
| errores_5xx | tasa 5xx | > 1 % | 1 lote | Alta | Plataforma | Revisar el servicio / activar respaldo |
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from monitoreo.deriva import cargar_referencia, chi2_categorica, ks_por_feature, psi_por_feature
from src import almacen
from src.business_metrics import corridas_evitadas, elution_order_accuracy
from src.pipeline import MOLECULE_FEATURE_COLUMNS, MoleculeConditionFeatures, METHOD_RAW_COLUMNS
from src.simulacion import HORIZONTE_LOTES

N_LOTES = 10
PLANTILLA = {
    "desempeno_rmse": ("1 lote", "Alta", "Ciencia de datos", "Diagnosticar; con 2 lotes seguidos se reentrena"),
    "desempeno_sesgo": ("1 lote", "Alta", "Ciencia de datos + laboratorio", "Revisar equipo y método (volumen de retardo, temperatura); con 2 lotes seguidos se reentrena"),
    "deriva_datos": ("1 lote", "Media", "Equipo de datos", "Revisar la fuente; no reentrenar si el desempeño se mantiene"),
    "fuera_de_dominio": ("1 lote", "Alta", "Analistas + ciencia de datos", "Confirmar con corrida exploratoria; incorporar esos métodos al reentrenar"),
    "categoria_no_vista": ("1 lote", "Baja", "Equipo de datos", "Informativa: ampliar el catálogo de columnas y fases"),
    "latencia_p95": ("1 lote", "Media", "Plataforma", "Escalar el servicio"),
    "errores_4xx": ("1 lote", "Media", "Equipo de datos", "Revisar la calidad de las solicitudes"),
    "errores_5xx": ("1 lote", "Alta", "Plataforma", "Revisar el servicio o activar el respaldo"),
    "reentrenamiento": ("2 lotes consecutivos", "Alta", "Ciencia de datos", "Lanzar reentrenamiento.yml (challenger + aprobación humana)"),
}


def _fila(semana, lote_eval, tipo, metrica, valor, umbral=None, feature=None, version=None):
    valor = None if valor is None or (isinstance(valor, float) and not np.isfinite(valor)) else float(valor)
    supera = None if umbral is None or valor is None else bool(valor > umbral)
    return {"lote": semana, "lote_evaluado": lote_eval, "tipo": tipo, "metrica": metrica,
            "feature": feature, "valor": valor, "umbral": umbral, "supera": supera, "version_modelo": version}


def _info_version(version: int) -> dict[str, Any]:
    from mlflow.tracking import MlflowClient

    from src.experiments import configure_tracking
    from src.reentrenar import BASELINE_ARTIFACT, MODEL_NAME

    configure_tracking()
    client = MlflowClient()
    mv = client.get_model_version(MODEL_NAME, str(version))
    metricas = client.get_run(mv.run_id).data.metrics
    base = json.loads(open(client.download_artifacts(mv.run_id, BASELINE_ARTIFACT), encoding="utf-8").read())
    return {"intervalo": (metricas["pair_lower_error_quantile"], metricas["pair_upper_error_quantile"]),
            "cv_media": metricas["cv_rmse_mean"], "cv_de": metricas["cv_rmse_std"], "linea_base": base}


def metricas_lote_actual(semana: int, ref: dict[str, Any]) -> list[dict]:
    U = ref["umbrales"]
    sol = almacen.consultar("SELECT * FROM SOLICITUDES WHERE LOTE = %s", (semana,))
    pred = almacen.consultar("SELECT * FROM PREDICCIONES WHERE LOTE = %s", (semana,))
    ent = almacen.consultar("SELECT * FROM LOTES_ENTRADAS WHERE LOTE = %s", (semana,))
    version = int(pred["version_modelo"].dropna().mode().iloc[0]) if pred["version_modelo"].notna().any() else None
    f = lambda *a, **k: _fila(semana, None, *a, version=version, **k)
    ok = sol[sol["status"] == 200]
    filas = [
        f("sistema", "solicitudes", len(sol)),
        f("sistema", "predicciones", len(pred)),
        f("sistema", "latencia_p50_ms", ok["latencia_ms"].quantile(0.5) if len(ok) else None),
        f("sistema", "latencia_p95_ms", ok["latencia_ms"].quantile(0.95) if len(ok) else None, U["latencia_p95_ms"]),
        f("sistema", "tasa_4xx", ((sol["status"] >= 400) & (sol["status"] < 500)).mean(), U["tasa_4xx"]),
        f("sistema", "tasa_5xx", (sol["status"] >= 500).mean(), U["tasa_5xx"]),
    ]
    if len(pred):
        p = pred["prediccion_min"]
        filas += [f("modelo", f"prediccion_{n}", v) for n, v in
                  (("media", p.mean()), ("p10", p.quantile(.1)), ("p50", p.median()), ("p90", p.quantile(.9)))]
        filas += [
            f("modelo", "tasa_revisar", (pred["decision"] == "revisar_condiciones").mean()),
            f("modelo", "tasa_aprobar", (pred["decision"] == "aprobar_condiciones").mean()),
            f("modelo", "tasa_respaldo", pred["respaldo_usado"].mean()),
            f("datos", "fraccion_fuera_de_dominio", pred["fuera_de_dominio"].mean(), U["fraccion_fuera_de_dominio"]),
        ]
    # Datos: faltantes por feature (entradas del lote)
    for columna in ("flujo_ml_min", *[c for c in METHOD_RAW_COLUMNS]):
        filas.append(f("datos", "faltantes", ent[columna].isna().mean(), feature=columna))
    for columna in ("tipo_columna", "fase_movil"):
        p_chi, frac, n_nuevas = chi2_categorica(ref["categorias"][columna], ent[columna])
        filas += [f("datos", "categoria_no_vista", frac, U["fraccion_categoria_no_vista"], feature=columna),
                  f("deriva", "chi2_p", p_chi, feature=columna)]
    # Deriva de datos: PSI (decide) + KS (respaldo) en descriptores moleculares
    X = ent.rename(columns=str.lower)
    feats = MoleculeConditionFeatures().fit(X).transform(X)[list(MOLECULE_FEATURE_COLUMNS)]
    psis = psi_por_feature(ref, feats)
    ks = ks_por_feature(pd.DataFrame(ref["muestra_ks"]), feats)
    sobre = 0
    for feature, valor in psis.items():
        umbral = U["psi"][feature]
        sobre += valor > umbral
        filas += [f("deriva", "psi", valor, umbral, feature=feature), f("deriva", "ks_p", ks.get(feature), feature=feature)]
    respaldo_ks = sum(ks.get(ft, 1) < U["ks_p_valor"] for ft, v in psis.items() if v > U["psi"][ft])
    filas += [f("deriva", "psi_features_sobre_umbral", sobre, U["psi_features_para_alerta"] - 0.5),
              f("deriva", "psi_sobre_umbral_confirmadas_ks", respaldo_ks)]
    return filas


def metricas_desempeno(semana: int, ref: dict[str, Any]) -> list[dict]:
    lote = semana - HORIZONTE_LOTES
    if lote < 1:
        return []
    U = ref["umbrales"]
    datos = almacen.consultar(
        """SELECT p.HECHO_ID, p.EXPERIMENTO_ID, p.PREDICCION_MIN, p.VERSION_MODELO, p.TIPO_COLUMNA,
                  p.FASE_MOVIL, p.FLUJO_ML_MIN, t.TIEMPO_RETENCION
           FROM PREDICCIONES p JOIN TARGETS t ON p.HECHO_ID = t.HECHO_ID AND p.LOTE = t.LOTE
           WHERE p.LOTE = %s""",
        (lote,),
    )
    if datos.empty:
        return []
    version = int(datos["version_modelo"].mode().iloc[0])
    info = _info_version(version)
    f = lambda *a, **k: _fila(semana, lote, *a, version=version, **k)
    y, p = datos["tiempo_retencion"].to_numpy(), datos["prediccion_min"].to_numpy()
    rmse, sesgo = float(np.sqrt(np.mean((p - y) ** 2))), float(np.mean(p - y))
    from src.reentrenar import baseline_predict

    base = baseline_predict(info["linea_base"], datos)
    negocio = corridas_evitadas(y, p, datos["experimento_id"], info["intervalo"])
    orden = elution_order_accuracy(y, p, datos["experimento_id"])
    return [
        f("desempeno", "n_con_target", len(datos)),
        f("desempeno", "rmse", rmse, U["rmse_lote"]),
        f("desempeno", "mae", float(np.mean(np.abs(p - y)))),
        f("desempeno", "sesgo", sesgo),
        f("desempeno", "sesgo_abs", abs(sesgo), U["sesgo_abs_lote"]),
        f("desempeno", "z_vs_cv", (rmse - info["cv_media"]) / info["cv_de"]),
        f("desempeno", "rmse_linea_base", float(np.sqrt(np.mean((base - y) ** 2)))),
        f("desempeno", "orden_exactitud_2min", orden["orden_exactitud"]),
        f("negocio", "corridas_evitadas_netas", negocio["neto"]),
        f("negocio", "tasa_aprobacion", negocio["tasa_aprobacion"]),
        f("negocio", "aprobaciones_fallidas", negocio["fallo"]),
        f("negocio", "neto_linea_base", 0.0),  # la mediana por condición nunca aprueba: revisar siempre
        f("negocio", "neto_aprobar_todo", negocio["neto_aprobar_todo"]),
        f("negocio", "tasa_metodos_separables", negocio["tasa_separable"]),
        f("desempeno", "alerta_desempeno", float(rmse > U["rmse_lote"] or abs(sesgo) > U["sesgo_abs_lote"])),
    ]


def _alertas(semana: int, filas: list[dict], ref: dict[str, Any]) -> list[dict]:
    U = ref["umbrales"]
    m = pd.DataFrame(filas)
    get = lambda met, feat=None: m[(m.metrica == met) & (m.feature.isna() if feat is None else m.feature == feat)]
    alertas = []

    def alerta(nombre, metrica, valor, umbral, lote_eval=None, diagnostico=None):
        ventana, severidad, receptor, accion = PLANTILLA[nombre]
        alertas.append({"lote": semana, "lote_evaluado": lote_eval, "alerta": nombre, "metrica": metrica,
                        "valor": valor, "umbral": umbral, "ventana": ventana, "severidad": severidad,
                        "receptor": receptor, "accion": accion, "diagnostico": diagnostico})

    for nombre, met in (("latencia_p95", "latencia_p95_ms"), ("errores_4xx", "tasa_4xx"), ("errores_5xx", "tasa_5xx"),
                        ("fuera_de_dominio", "fraccion_fuera_de_dominio")):
        r = get(met)
        if len(r) and r.supera.iloc[0]:
            alerta(nombre, met, r.valor.iloc[0], r.umbral.iloc[0])
    for _, r in m[(m.metrica == "categoria_no_vista") & (m.supera == True)].iterrows():  # noqa: E712
        alerta("categoria_no_vista", f"categoria_no_vista:{r.feature}", r.valor, r.umbral)
    datos_cambian = False
    r = get("psi_features_sobre_umbral")
    if len(r) and r.valor.iloc[0] >= U["psi_features_para_alerta"]:
        datos_cambian = True
        feats = ", ".join(m[(m.metrica == "psi") & (m.supera == True)].feature)  # noqa: E712
        alerta("deriva_datos", f"psi ({feats})", r.valor.iloc[0], U["psi_features_para_alerta"])
    # Desempeño del lote evaluado y diagnóstico con la deriva de datos de ESE lote
    d = m[m.tipo.isin(["desempeno"])]
    if len(d):
        lote_eval = int(d.lote_evaluado.iloc[0])
        previo = almacen.consultar(
            "SELECT VALOR FROM MONITOREO WHERE LOTE = %s AND METRICA IN ('psi_features_sobre_umbral', 'fraccion_fuera_de_dominio') ORDER BY METRICA",
            (lote_eval,),
        )
        fuera = float(previo.valor.iloc[0]) if len(previo) > 0 else 0.0
        psi_sobre = float(previo.valor.iloc[1]) if len(previo) > 1 else 0.0
        entradas_cambian = psi_sobre >= U["psi_features_para_alerta"] or fuera > U["fraccion_fuera_de_dominio"]
        rmse, sesgo_abs = get("rmse"), get("sesgo_abs")
        cae = bool(rmse.supera.iloc[0] or sesgo_abs.supera.iloc[0])
        diagnostico = (
            "deriva de datos con impacto" if entradas_cambian and cae else
            "deriva de datos sin impacto" if entradas_cambian else
            "deriva conceptual" if cae else "estable"
        )
        if rmse.supera.iloc[0]:
            alerta("desempeno_rmse", "rmse", rmse.valor.iloc[0], rmse.umbral.iloc[0], lote_eval, diagnostico)
        if sesgo_abs.supera.iloc[0]:
            alerta("desempeno_sesgo", "sesgo_abs", sesgo_abs.valor.iloc[0], sesgo_abs.umbral.iloc[0], lote_eval, diagnostico)
        m.loc[m.tipo == "desempeno", "diagnostico"] = diagnostico
        filas.append(_fila(semana, lote_eval, "desempeno", f"diagnostico:{diagnostico}", 1.0,
                           version=int(d.version_modelo.iloc[0])))
    return alertas


def decidir_reentrenamiento(semana: int, ref: dict[str, Any]) -> tuple[bool, str]:
    """Desempeño: alerta en N lotes evaluados consecutivos con el champion
    vigente. Calendario: cada K lotes evaluados desde el último reentrenamiento.
    La deriva de datos sola no dispara. Solo cuentan lotes con target."""
    U = ref["umbrales"]
    hist = almacen.consultar(
        "SELECT LOTE_EVALUADO, VALOR, VERSION_MODELO FROM MONITOREO WHERE METRICA = 'alerta_desempeno' ORDER BY LOTE_EVALUADO"
    )
    if hist.empty:
        return False, ""
    ultimo = almacen.consultar("SELECT COALESCE(MAX(LOTE), 0) AS L FROM REENTRENAMIENTOS")
    desde = int(ultimo.l.iloc[0])
    vigente = hist[(hist.version_modelo == hist.version_modelo.iloc[-1]) & (hist.lote_evaluado >= desde)]
    n = U["lotes_consecutivos_reentrenamiento"]
    if len(vigente) >= n and (vigente.valor.tail(n) == 1).all():
        lotes = ", ".join(str(int(x)) for x in vigente.lote_evaluado.tail(n))
        return True, f"desempeño: alerta de RMSE o sesgo en {n} lotes consecutivos ({lotes})"
    evaluados = hist[hist.lote_evaluado > desde]
    if len(evaluados) >= U["reentrenamiento_calendario_lotes"]:
        return True, f"calendario: {len(evaluados)} lotes evaluados desde el último reentrenamiento"
    return False, ""


def monitorear(semana: int) -> dict[str, Any]:
    ref = cargar_referencia()
    filas = metricas_lote_actual(semana, ref) if semana <= N_LOTES else []
    filas += metricas_desempeno(semana, ref)
    alertas = _alertas(semana, filas, ref)
    ts = datetime.now(timezone.utc)
    almacen.escribir("MONITOREO", pd.DataFrame(filas).assign(ts=ts), borrar_donde=f"LOTE = {semana}")
    reentrenar, motivo = decidir_reentrenamiento(semana, ref)
    if reentrenar:
        ventana, severidad, receptor, accion = PLANTILLA["reentrenamiento"]
        alertas.append({"lote": semana, "lote_evaluado": semana - HORIZONTE_LOTES, "alerta": "reentrenamiento",
                        "metrica": "alerta_desempeno", "valor": 1.0, "umbral": None, "ventana": ventana,
                        "severidad": severidad, "receptor": receptor, "accion": accion, "diagnostico": motivo})
    almacen.escribir("ALERTAS", pd.DataFrame(alertas).assign(ts=ts), borrar_donde=f"LOTE = {semana}")
    for a in alertas:
        print(f"[ALERTA {a['severidad'].upper()}] semana {semana} · {a['alerta']} · {a['metrica']}={a['valor']} "
              f"(umbral {a['umbral']}) → {a['receptor']}: {a['accion']}" + (f" · {a['diagnostico']}" if a["diagnostico"] else ""))
    if not alertas:
        print(f"Semana {semana}: sin alertas")
    resumen = {"semana": semana, "alertas": len(alertas), "reentrenar": reentrenar, "motivo": motivo}
    print("::" + json.dumps({"outputs": resumen}) + "::")
    return resumen


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semana", type=int, required=True)
    monitorear(parser.parse_args().semana)
