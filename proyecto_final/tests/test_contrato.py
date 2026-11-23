"""Contrato de la API: 200 con el esquema esperado; 422 con el campo que falló."""

from __future__ import annotations

import copy

import pytest

CAMPOS_RESPUESTA = {
    "id_solicitud", "decision", "accion", "predicciones", "pares_en_riesgo",
    "orden_elucion", "modelo", "version_modelo", "alias", "run_id",
    "respaldo_usado", "advertencias", "latencia_ms",
}


def test_entrada_valida_devuelve_200_con_el_esquema(cliente, solicitud_valida, metadata_modelo):
    r = cliente.post("/predecir", json=solicitud_valida)
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == CAMPOS_RESPUESTA
    assert cuerpo["decision"] in {"aprobar_condiciones", "revisar_condiciones"}
    assert cuerpo["accion"]
    assert cuerpo["version_modelo"] == metadata_modelo["version"]
    assert cuerpo["run_id"] == metadata_modelo["run_id"]
    assert cuerpo["respaldo_usado"] is False
    assert [p["id"] for p in cuerpo["predicciones"]] == ["cafeina", "ibuprofeno", "tolueno"]
    assert all(p["tiempo_retencion_min"] > 0 and p["id_prediccion"] for p in cuerpo["predicciones"])
    assert len(cuerpo["orden_elucion"]) == 2


def test_un_solo_compuesto_se_aprueba(cliente, solicitud_valida):
    solicitud_valida["compuestos"] = solicitud_valida["compuestos"][:1]
    r = cliente.post("/predecir", json=solicitud_valida)
    assert r.status_code == 200
    assert r.json()["decision"] == "aprobar_condiciones"


def _sin(dic, campo):
    dic = copy.deepcopy(dic)
    dic.pop(campo)
    return dic


@pytest.mark.parametrize(
    ("modificar", "campo_esperado"),
    [
        # campo faltante
        (lambda s: _sin(s, "fase_movil"), "fase_movil"),
        (lambda s: {**s, "compuestos": [{"id": "x"}]}, "compuestos.0.smiles"),
        # tipo incorrecto
        (lambda s: {**s, "flujo_ml_min": "rapido"}, "flujo_ml_min"),
        (lambda s: {**s, "compuestos": "Cc1ccccc1"}, "compuestos"),
        # categoría desconocida / fuera de alcance
        (lambda s: {**s, "tipo_columna": "Phenomenex Luna C8"}, "tipo_columna"),
        (lambda s: {**s, "fase_movil": "A[agua] B[metanol]"}, "fase_movil"),
        # rango
        (lambda s: {**s, "flujo_ml_min": -0.2}, "flujo_ml_min"),
        (lambda s: {**s, "fase_movil": "A[H2O=100; MeOH=0; ACN=0] B[H2O=0; MeOH=0; ACN=150]"}, "fase_movil"),
        # SMILES químicamente inválido
        (lambda s: {**s, "compuestos": [{"id": "x", "smiles": "C1CC(("}]}, "compuestos.0.smiles"),
    ],
)
def test_entrada_invalida_devuelve_422_con_el_campo(cliente, solicitud_valida, modificar, campo_esperado):
    r = cliente.post("/predecir", json=modificar(solicitud_valida))
    assert r.status_code == 422
    campos = [e["campo"] for e in r.json()["errores"]]
    assert any(c.startswith(campo_esperado) for c in campos), campos
    assert campo_esperado.split(".")[0] in r.json()["mensaje"]


def test_salud_y_modelo(cliente, metadata_modelo):
    salud = cliente.get("/salud").json()
    assert salud == {**salud, "estado": "ok", "modelo_cargado": True}
    info = cliente.get("/modelo").json()
    assert info["nombre"] == "qsrr-predict-modelo"
    assert info["version"] == metadata_modelo["version"]
    assert info["alias"] == "champion"
    assert info["run_id"] == metadata_modelo["run_id"]


def test_advertencia_para_categoria_no_vista(cliente, solicitud_valida):
    solicitud_valida["tipo_columna"] = "Marca Nueva XYZ C18"
    r = cliente.post("/predecir", json=solicitud_valida)
    assert r.status_code == 200
    assert "tipo_columna no vista en entrenamiento" in r.json()["advertencias"]
