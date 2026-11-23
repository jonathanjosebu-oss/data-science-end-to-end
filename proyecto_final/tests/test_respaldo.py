"""Respaldo (PSet 4 §3.4 y §8.4): sin modelo, o con el interruptor activo, la
API responde con la línea base del PSet 3 (mediana por condición) y lo indica."""

from __future__ import annotations

import pytest

import api.main as servicio

TOKEN = {"x-admin-token": "token-de-prueba"}


@pytest.fixture()
def sin_modelo(monkeypatch):
    """Simula que el modelo no cargó (URI inexistente)."""
    almacen = servicio.AlmacenModelo()
    almacen.uri = "ruta/que/no/existe"
    almacen.cargar()
    monkeypatch.setattr(servicio, "almacen", almacen)
    return almacen


def test_si_el_modelo_no_carga_responde_la_linea_base(cliente, solicitud_valida, sin_modelo):
    assert sin_modelo.modelo is None and sin_modelo.error
    salud = cliente.get("/salud").json()
    assert salud["estado"] == "degradado" and salud["respaldo_activo"] is True

    r = cliente.post("/predecir", json=solicitud_valida)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["respaldo_usado"] is True
    assert cuerpo["advertencias"][0].startswith("respaldo")
    # La mediana por condición da el mismo tiempo a todos los analitos del
    # método: la decisión conservadora es revisar.
    tiempos = {p["tiempo_retencion_min"] for p in cuerpo["predicciones"]}
    assert len(tiempos) == 1
    assert cuerpo["decision"] == "revisar_condiciones"
    assert not any(par["orden_confiable"] for par in cuerpo["orden_elucion"])


def test_interruptor_activa_y_desactiva_el_respaldo(cliente, solicitud_valida):
    try:
        r = cliente.post("/admin/respaldo", params={"activo": True}, headers=TOKEN)
        assert r.status_code == 200 and r.json()["respaldo_activo"] is True
        assert cliente.post("/predecir", json=solicitud_valida).json()["respaldo_usado"] is True
        assert cliente.get("/modelo").json()["respaldo_activo"] is True
    finally:
        cliente.post("/admin/respaldo", params={"activo": False}, headers=TOKEN)
    assert cliente.post("/predecir", json=solicitud_valida).json()["respaldo_usado"] is False


def test_interruptor_exige_token(cliente):
    assert cliente.post("/admin/respaldo", params={"activo": True}).status_code == 403
    assert cliente.post(
        "/admin/respaldo", params={"activo": True}, headers={"x-admin-token": "otro"}
    ).status_code == 403
