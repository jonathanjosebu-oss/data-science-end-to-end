"""Servicio de predicción QSRR-Predict (FastAPI).

Acción del PSet 1: aprobar o revisar unas condiciones cromatográficas antes de
preparar los reactivos. Para un método y sus analitos, la API predice el tiempo
de retención de cada uno y alerta coelución entre picos adyacentes con el
intervalo del 95 % calibrado en el PSet 3 (umbral de decisión).

Variables de entorno:
  MODELO_URI         models:/qsrr-predict-modelo@champion (o ruta local de un
                     modelo guardado con mlflow.sklearn.save_model, p. ej. en CI)
  MODELO_METADATA    JSON con versión/run_id/intervalo cuando MODELO_URI es local
  LINEA_BASE_PATH    JSON de la línea base (respaldo) empaquetado en la imagen
  USAR_RESPALDO      "true" fuerza la regla de negocio en lugar del modelo
  ADMIN_TOKEN        protege /admin/*; sin token esos endpoints quedan cerrados
  MODELO_TTL_S       cada cuántos segundos se revisa si el alias cambió (30)
  REGISTROS_DIR      carpeta de los registros JSONL de predicciones y solicitudes
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.esquemas import (
    EstadoSalud,
    InfoModelo,
    ParAdyacente,
    ParEnRiesgo,
    PrediccionCompuesto,
    RespuestaPrediccion,
    SolicitudPrediccion,
)
from src.business_metrics import ORDEN_CONFIABLE_MIN
from src.pipeline import RAW_FEATURE_COLUMNS
from src.reentrenar import BASELINE_ARTIFACT, MODEL_NAME, baseline_predict
from src.reentrenar import DOMAIN_ARTIFACT as DOMINIO_ARTIFACT


def _env_bool(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "si", "sí", "yes"}


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


class AlmacenModelo:
    """Carga el modelo por alias y lo recarga cuando el alias apunta a otra versión."""

    def __init__(self) -> None:
        self.uri = os.getenv("MODELO_URI", f"models:/{MODEL_NAME}@champion")
        self.ttl = float(os.getenv("MODELO_TTL_S", "30"))
        self.respaldo_forzado = _env_bool("USAR_RESPALDO")
        self.modelo: Any = None
        self.version: int | None = None
        self.alias: str | None = None
        self.run_id: str | None = None
        self.intervalo = (float("nan"), float("nan"))
        self.dominio: dict[str, Any] = {}
        self.linea_base: dict[str, Any] | None = None
        self.cargado_en: str | None = None
        self.error: str | None = None
        self._revisado = 0.0
        self._lock = threading.Lock()
        self._cargar_linea_base_local()

    # -- carga ---------------------------------------------------------------
    def _cargar_linea_base_local(self) -> None:
        path = Path(os.getenv("LINEA_BASE_PATH", "/app/linea_base.json"))
        if path.is_file():
            self.linea_base = json.loads(path.read_text(encoding="utf-8"))

    def _desde_registro(self) -> None:
        import mlflow.sklearn
        from mlflow.tracking import MlflowClient

        nombre, alias = self.uri.removeprefix("models:/").split("@", 1)
        client = MlflowClient()
        mv = client.get_model_version_by_alias(nombre, alias)
        modelo = mlflow.sklearn.load_model(f"models:/{nombre}/{mv.version}")
        run = client.get_run(mv.run_id)
        artefactos = {}
        for nombre_artefacto in (BASELINE_ARTIFACT, DOMINIO_ARTIFACT):
            try:
                ruta = client.download_artifacts(mv.run_id, nombre_artefacto)
                artefactos[nombre_artefacto] = json.loads(Path(ruta).read_text("utf-8"))
            except Exception:  # artefacto opcional
                pass
        self.modelo, self.version, self.alias, self.run_id = (
            modelo, int(mv.version), alias, mv.run_id,
        )
        metricas = run.data.metrics
        self.intervalo = (
            metricas["pair_lower_error_quantile"],
            metricas["pair_upper_error_quantile"],
        )
        self.dominio = artefactos.get(DOMINIO_ARTIFACT, {})
        if BASELINE_ARTIFACT in artefactos:
            self.linea_base = artefactos[BASELINE_ARTIFACT]

    def _desde_archivo(self) -> None:
        import mlflow.sklearn

        self.modelo = mlflow.sklearn.load_model(self.uri)
        meta_path = os.getenv("MODELO_METADATA")
        meta = json.loads(Path(meta_path).read_text("utf-8")) if meta_path else {}
        self.version = meta.get("version")
        self.alias = meta.get("alias")
        self.run_id = meta.get("run_id")
        self.intervalo = (
            meta.get("pair_lower_error_quantile", float("nan")),
            meta.get("pair_upper_error_quantile", float("nan")),
        )
        self.dominio = meta.get("dominio", {})

    def cargar(self) -> None:
        with self._lock:
            try:
                if self.uri.startswith("models:/"):
                    self._desde_registro()
                else:
                    self._desde_archivo()
                self.cargado_en = _ahora()
                self.error = None
            except Exception as exc:  # el servicio sigue vivo con el respaldo
                self.modelo = None
                self.error = f"{type(exc).__name__}: {exc}"[:300]
            self._revisado = time.monotonic()

    def revisar_alias(self, forzar: bool = False) -> None:
        """Recarga si el alias se movió (promoción o rollback) o si no hay modelo."""
        if not forzar and time.monotonic() - self._revisado < self.ttl:
            return
        if not self.uri.startswith("models:/"):
            if self.modelo is None:
                self.cargar()
            return
        try:
            from mlflow.tracking import MlflowClient

            nombre, alias = self.uri.removeprefix("models:/").split("@", 1)
            actual = int(MlflowClient().get_model_version_by_alias(nombre, alias).version)
        except Exception:
            actual = None
        if forzar or self.modelo is None or (actual is not None and actual != self.version):
            self.cargar()
        else:
            self._revisado = time.monotonic()

    # -- estado --------------------------------------------------------------
    @property
    def usa_respaldo(self) -> bool:
        return self.respaldo_forzado or self.modelo is None


class Registro:
    """Registros append-only (JSONL). Kestra los carga a Snowflake por lote."""

    def __init__(self) -> None:
        self.dir = Path(os.getenv("REGISTROS_DIR", "/app/registros"))
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.recientes: deque[dict[str, Any]] = deque(maxlen=5_000)

    def _escribir(self, archivo: str, filas: list[dict[str, Any]]) -> None:
        with self._lock, (self.dir / archivo).open("a", encoding="utf-8") as fh:
            for fila in filas:
                fh.write(json.dumps(fila, ensure_ascii=False, default=str) + "\n")

    def prediccion(self, filas: list[dict[str, Any]]) -> None:
        self._escribir("predicciones.jsonl", filas)

    def solicitud(self, fila: dict[str, Any]) -> None:
        self.recientes.append(fila)
        self._escribir("solicitudes.jsonl", [fila])


almacen = AlmacenModelo()
registro = Registro()


@asynccontextmanager
async def _ciclo_de_vida(_: FastAPI):
    almacen.cargar()
    yield


app = FastAPI(
    title="QSRR-Predict",
    version="1.0",
    description="Tiempo de retención en C18 y alerta de coelución antes de preparar reactivos.",
    lifespan=_ciclo_de_vida,
)


@app.middleware("http")
async def _metricas_sistema(request: Request, call_next):
    inicio = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        registro.solicitud(
            {
                "ts": _ahora(),
                "metodo": request.method,
                "ruta": request.url.path,
                "status": status,
                "latencia_ms": round((time.perf_counter() - inicio) * 1000, 3),
            }
        )


@app.exception_handler(RequestValidationError)
async def _entrada_invalida(request: Request, exc: RequestValidationError):
    errores = [
        {
            "campo": ".".join(str(p) for p in err["loc"] if p != "body"),
            "error": err["msg"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "mensaje": "Entrada inválida: " + "; ".join(f"{e['campo']}: {e['error']}" for e in errores),
            "errores": errores,
        },
    )


@app.get("/salud", response_model=EstadoSalud)
def salud() -> EstadoSalud:
    almacen.revisar_alias()
    cargado = almacen.modelo is not None
    return EstadoSalud(
        estado="ok" if cargado else "degradado",
        modelo_cargado=cargado,
        respaldo_activo=almacen.usa_respaldo,
        detalle=almacen.error,
    )


@app.get("/modelo", response_model=InfoModelo)
def modelo() -> InfoModelo:
    almacen.revisar_alias()
    return InfoModelo(
        nombre=MODEL_NAME,
        version=almacen.version,
        alias=almacen.alias,
        run_id=almacen.run_id,
        fuente=almacen.uri,
        respaldo_activo=almacen.usa_respaldo,
        cargado_en_utc=almacen.cargado_en,
    )


def _advertencias(solicitud: SolicitudPrediccion) -> list[str]:
    dominio = almacen.dominio
    avisos = []
    if dominio.get("tipo_columna") and solicitud.tipo_columna not in dominio["tipo_columna"]:
        avisos.append("tipo_columna no vista en entrenamiento")
    if dominio.get("fase_movil") and solicitud.fase_movil not in dominio["fase_movil"]:
        avisos.append("fase_movil no vista en entrenamiento")
    rango = dominio.get("flujo_ml_min")
    if solicitud.flujo_ml_min is None:
        avisos.append("flujo_ml_min faltante: se imputa con la mediana de entrenamiento")
    elif rango and not rango[0] <= solicitud.flujo_ml_min <= rango[1]:
        avisos.append("flujo_ml_min fuera del rango de entrenamiento")
    return avisos


def _pares_en_riesgo(ids: list[str], pred: np.ndarray) -> list[ParEnRiesgo]:
    """Picos adyacentes cuyo intervalo de la diferencia contiene 0 (PSet 3)."""
    inferior, superior = almacen.intervalo
    if not np.isfinite(inferior) or not np.isfinite(superior):
        inferior, superior = -np.inf, np.inf  # sin calibración: alerta conservadora
    orden = np.argsort(pred, kind="mergesort")
    pares = []
    for a, b in zip(orden[:-1], orden[1:]):
        delta = float(pred[b] - pred[a])
        if delta + inferior <= 0 <= delta + superior:
            pares.append(ParEnRiesgo(compuesto_a=ids[a], compuesto_b=ids[b], diferencia_predicha_min=round(delta, 4)))
    return pares


@app.post("/predecir", response_model=RespuestaPrediccion)
def predecir(solicitud: SolicitudPrediccion) -> RespuestaPrediccion:
    inicio = time.perf_counter()
    almacen.revisar_alias()
    ids = [c.id for c in solicitud.compuestos]
    entrada = pd.DataFrame(
        {
            "smiles": [c.smiles for c in solicitud.compuestos],
            "tipo_columna": solicitud.tipo_columna,
            "fase_movil": solicitud.fase_movil,
            "flujo_ml_min": np.nan if solicitud.flujo_ml_min is None else solicitud.flujo_ml_min,
        }
    ).loc[:, list(RAW_FEATURE_COLUMNS)]
    respaldo = almacen.usa_respaldo
    if respaldo:
        if almacen.linea_base is None:
            raise HTTPException(503, "Modelo no disponible y sin línea base de respaldo")
        pred = baseline_predict(almacen.linea_base, entrada)
    else:
        pred = np.asarray(almacen.modelo.predict(entrada), dtype=float)

    pares = _pares_en_riesgo(ids, pred)
    orden = np.argsort(pred, kind="mergesort")
    orden_elucion = [
        ParAdyacente(
            primero=ids[a],
            segundo=ids[b],
            diferencia_predicha_min=round(float(pred[b] - pred[a]), 4),
            orden_confiable=(not respaldo) and float(pred[b] - pred[a]) >= ORDEN_CONFIABLE_MIN,
        )
        for a, b in zip(orden[:-1], orden[1:])
    ]
    if pares:
        decision = "revisar_condiciones"
        accion = (
            f"No preparar reactivos todavía: {len(pares)} par(es) de picos adyacentes con riesgo "
            "de coelución. El analista ajusta gradiente, fase móvil o columna, o confirma con una corrida exploratoria."
        )
    else:
        decision = "aprobar_condiciones"
        accion = "Preparar reactivos e inyectar: no se predice coelución entre picos adyacentes. El analista valida antes de correr."
    advertencias = _advertencias(solicitud)
    if respaldo:
        advertencias.insert(0, "respaldo: predicción con la línea base (mediana por condición), no con el modelo")

    id_solicitud = str(uuid.uuid4())
    ts = _ahora()
    latencia = round((time.perf_counter() - inicio) * 1000, 3)
    predicciones = [
        PrediccionCompuesto(id_prediccion=str(uuid.uuid4()), id=i, tiempo_retencion_min=round(float(p), 4))
        for i, p in zip(ids, pred)
    ]
    registro.prediccion(
        [
            {
                "id_prediccion": p.id_prediccion,
                "id_solicitud": id_solicitud,
                "ts": ts,
                "lote": solicitud.lote,
                "compuesto_id": p.id,
                "smiles": c.smiles,
                "tipo_columna": solicitud.tipo_columna,
                "fase_movil": solicitud.fase_movil,
                "flujo_ml_min": solicitud.flujo_ml_min,
                "prediccion_min": p.tiempo_retencion_min,
                "decision": decision,
                "respaldo_usado": respaldo,
                "modelo": MODEL_NAME,
                "version_modelo": almacen.version,
                "alias": almacen.alias,
                "run_id": almacen.run_id,
                "latencia_ms": latencia,
                "advertencias": "|".join(advertencias),
            }
            for p, c in zip(predicciones, solicitud.compuestos)
        ]
    )
    return RespuestaPrediccion(
        id_solicitud=id_solicitud,
        decision=decision,
        accion=accion,
        predicciones=predicciones,
        pares_en_riesgo=pares,
        orden_elucion=orden_elucion,
        modelo=MODEL_NAME,
        version_modelo=None if respaldo else almacen.version,
        alias=None if respaldo else almacen.alias,
        run_id=None if respaldo else almacen.run_id,
        respaldo_usado=respaldo,
        advertencias=advertencias,
        latencia_ms=latencia,
    )


@app.get("/metricas")
def metricas() -> dict[str, Any]:
    """Métricas de sistema sobre las solicitudes recientes a /predecir."""
    filas = [f for f in registro.recientes if f["ruta"] == "/predecir"]
    if not filas:
        return {"solicitudes": 0}
    lat = np.array([f["latencia_ms"] for f in filas])
    status = np.array([f["status"] for f in filas])
    return {
        "solicitudes": int(len(filas)),
        "latencia_p50_ms": float(np.percentile(lat, 50)),
        "latencia_p95_ms": float(np.percentile(lat, 95)),
        "tasa_4xx": float(((status >= 400) & (status < 500)).mean()),
        "tasa_5xx": float((status >= 500).mean()),
    }


def _verificar_admin(token: str | None) -> None:
    esperado = os.getenv("ADMIN_TOKEN")
    if not esperado or token != esperado:
        raise HTTPException(status_code=403, detail="Token de administración inválido")


@app.post("/admin/respaldo")
def interruptor_respaldo(activo: bool, x_admin_token: str | None = Header(None)) -> dict[str, Any]:
    """Interruptor de respaldo (PSet 4 §8.4): usar la regla de negocio en vez del modelo."""
    _verificar_admin(x_admin_token)
    almacen.respaldo_forzado = activo
    return {"respaldo_activo": almacen.usa_respaldo, "cambiado_en_utc": _ahora()}


@app.post("/admin/recargar")
def recargar(x_admin_token: str | None = Header(None)) -> InfoModelo:
    """Fuerza la lectura del alias (sin esperar el TTL), p. ej. tras un rollback."""
    _verificar_admin(x_admin_token)
    almacen.revisar_alias(forzar=True)
    return modelo()
