"""Contrato de la API: coincide con la firma registrada en MLflow.

Firma del modelo (entrada cruda): smiles (str), tipo_columna (str),
fase_movil (str), flujo_ml_min (double, admite nulo: el pipeline lo imputa).

Reglas duras (422): lo que el modelo no puede o no debe puntuar.
Reglas blandas (advertencia): lo que puntúa pero fuera de lo visto en
entrenamiento; se registra y lo cuenta el monitoreo de datos.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

FASE_MOVIL_PATRON = re.compile(
    r"^A\[H2O=(?P<a_h2o>[^;\]]+); MeOH=(?P<a_meoh>[^;\]]+); ACN=(?P<a_acn>[^;\]]+)\] "
    r"B\[H2O=(?P<b_h2o>[^;\]]+); MeOH=(?P<b_meoh>[^;\]]+); ACN=(?P<b_acn>[^;\]]+)\]$"
)
FLUJO_MAX_ML_MIN = 5.0  # techo físico de un HPLC/UHPLC analítico
MAX_COMPUESTOS = 200


class Compuesto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=64, description="Identificador del analito")
    smiles: str = Field(..., min_length=1, max_length=500)

    @field_validator("smiles")
    @classmethod
    def smiles_valido(cls, value: str) -> str:
        value = value.strip()
        if Chem.MolFromSmiles(value) is None:
            raise ValueError("SMILES no interpretable por RDKit")
        return value


class SolicitudPrediccion(BaseModel):
    """Un método cromatográfico y los analitos que debe separar."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "tipo_columna": "Waters ACQUITY UPLC BEH C18",
                "fase_movil": "A[H2O=100; MeOH=0; ACN=0] B[H2O=0; MeOH=0; ACN=100]",
                "flujo_ml_min": 0.4,
                "compuestos": [
                    {"id": "cafeina", "smiles": "Cn1cnc2c1c(=O)n(C)c(=O)n2C"},
                    {"id": "ibuprofeno", "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O"},
                ],
            }
        },
    )

    tipo_columna: str = Field(..., min_length=3, max_length=120)
    fase_movil: str = Field(..., max_length=200)
    flujo_ml_min: float | None = Field(
        ..., gt=0, le=FLUJO_MAX_ML_MIN, description="mL/min; null si no se conoce"
    )
    compuestos: list[Compuesto] = Field(..., min_length=1, max_length=MAX_COMPUESTOS)
    lote: str | None = Field(
        None, max_length=40, description="Etiqueta del lote (solo simulación/auditoría)"
    )

    @field_validator("tipo_columna")
    @classmethod
    def solo_c18(cls, value: str) -> str:
        value = value.strip()
        if "C18" not in value.upper():
            raise ValueError("el modelo solo cubre columnas C18 (fuera de alcance)")
        return value

    @field_validator("fase_movil")
    @classmethod
    def fase_movil_valida(cls, value: str) -> str:
        match = FASE_MOVIL_PATRON.match(value.strip())
        if match is None:
            raise ValueError(
                "formato esperado: 'A[H2O=x; MeOH=y; ACN=z] B[H2O=x; MeOH=y; ACN=z]'"
            )
        valores = {}
        for nombre, texto in match.groupdict().items():
            try:
                numero = float(texto)
            except ValueError:
                raise ValueError(f"{nombre} no es numérico: {texto!r}") from None
            if not 0 <= numero <= 100:
                raise ValueError(f"{nombre} debe estar entre 0 y 100 (%)")
            valores[nombre] = numero
        for fase in ("a", "b"):
            total = sum(v for k, v in valores.items() if k.startswith(fase))
            if total > 100.5:
                raise ValueError(f"la fase {fase.upper()} suma {total:g} % (> 100 %)")
        return value.strip()

    @model_validator(mode="after")
    def ids_unicos(self) -> "SolicitudPrediccion":
        ids = [c.id for c in self.compuestos]
        if len(ids) != len(set(ids)):
            raise ValueError("compuestos: los id deben ser únicos")
        return self


class PrediccionCompuesto(BaseModel):
    id_prediccion: str
    id: str
    tiempo_retencion_min: float


class ParEnRiesgo(BaseModel):
    compuesto_a: str
    compuesto_b: str
    diferencia_predicha_min: float


class ParAdyacente(BaseModel):
    """Picos consecutivos en el orden predicho."""

    primero: str
    segundo: str
    diferencia_predicha_min: float
    orden_confiable: bool = Field(
        ..., description="Diferencia predicha >= 2 min: el orden acierta >= 91 % de las veces"
    )


Decision = Literal["aprobar_condiciones", "revisar_condiciones"]


class RespuestaPrediccion(BaseModel):
    id_solicitud: str
    decision: Decision
    accion: str
    predicciones: list[PrediccionCompuesto]
    pares_en_riesgo: list[ParEnRiesgo]
    orden_elucion: list[ParAdyacente]
    modelo: str
    version_modelo: int | None
    alias: str | None
    run_id: str | None
    respaldo_usado: bool
    advertencias: list[str]
    latencia_ms: float


class EstadoSalud(BaseModel):
    estado: Literal["ok", "degradado"]
    modelo_cargado: bool
    respaldo_activo: bool
    detalle: str | None = None


class InfoModelo(BaseModel):
    nombre: str
    version: int | None
    alias: str | None
    run_id: str | None
    fuente: str
    respaldo_activo: bool
    cargado_en_utc: str | None
