"""Zero-shot Gemini prediction requests for the bounded PSet 3 benchmark."""

from __future__ import annotations

import json
import math
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

PROMPT_VERSION = "retention-zero-shot-v1"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
_SYSTEM_INSTRUCTION = (
    "Estimate reversed-phase C18 chromatographic retention time in minutes. "
    "Use only the supplied molecular structure and method conditions. "
    "Do not claim experimental certainty. Return the requested JSON number."
)
_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"predicted_retention_min": {"type": "NUMBER"}},
    "required": ["predicted_retention_min"],
}


def build_prediction_prompt(row: Any) -> str:
    """Build a target-free prompt from inference-time molecular/method features."""
    required = ("smiles", "tipo_columna", "fase_movil", "flujo_ml_min")
    missing = [column for column in required if column not in row]
    if missing:
        raise ValueError(f"Missing prompt features: {missing}")

    return (
        "Return an object with one numeric field named "
        '"predicted_retention_min". Do not include an explanation.\n'
        f"SMILES: {row['smiles']}\n"
        f"Column: {row['tipo_columna']}\n"
        f"Mobile phase: {row['fase_movil']}\n"
        f"Flow rate (mL/min): {row['flujo_ml_min']}"
    )


def parse_prediction_response(response_text: str) -> float:
    """Validate the model's structured numeric prediction."""
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise ValueError("Gemini response is not valid JSON") from error
    if not isinstance(payload, dict) or "predicted_retention_min" not in payload:
        raise ValueError("Gemini response lacks predicted_retention_min")

    value = payload["predicted_retention_min"]
    if isinstance(value, bool):
        raise ValueError("Gemini prediction must be a finite number")
    try:
        prediction = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Gemini prediction must be a finite number") from error
    if not math.isfinite(prediction):
        raise ValueError("Gemini prediction must be a finite number")
    return prediction


def request_gemini_prediction(
    prompt: str,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    timeout: float = 60,
) -> dict[str, int | float | None]:
    """Call Gemini once, returning a validated prediction and token usage."""
    if not api_key:
        raise ValueError("A Gemini API key is required")
    if not model:
        raise ValueError("A Gemini model identifier is required")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{quote(model, safe='')}:generateContent"
    )
    body = {
        "systemInstruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 64,
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
        },
    }
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response_payload = json.loads(response.read())
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            f"Gemini API returned HTTP {error.code}: {detail}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"Gemini API request failed: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise ValueError("Gemini API returned invalid JSON") from error
    if not isinstance(response_payload, dict):
        raise ValueError("Gemini API response must be a JSON object")

    candidates = response_payload.get("candidates", [])
    if not candidates:
        feedback = response_payload.get("promptFeedback", {})
        raise ValueError(
            f"Gemini returned no candidates; prompt feedback: {feedback}"
        )
    parts = candidates[0].get("content", {}).get("parts", [])
    response_text = "".join(part.get("text", "") for part in parts)
    prediction = parse_prediction_response(response_text)

    usage = response_payload.get("usageMetadata", {})
    return {
        "prediction": prediction,
        "prompt_tokens": usage.get("promptTokenCount"),
        "output_tokens": usage.get("candidatesTokenCount"),
    }
