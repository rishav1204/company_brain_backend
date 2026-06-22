from __future__ import annotations

from typing import Any

FORBIDDEN_KEYS = frozenset(
    {
        "prompt",
        "chain_of_thought",
        "raw_llm_output",
        "full_prompt",
        "cot",
        "raw_reasoning",
    }
)


def validate_ai_context(context: dict[str, Any] | None) -> dict[str, Any]:
    if not context:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in context.items():
        lower = str(key).lower()
        if lower in FORBIDDEN_KEYS:
            raise ValueError(f"Forbidden AI context key: {key}")
        if isinstance(value, dict):
            cleaned[key] = validate_ai_context(value)
        elif isinstance(value, list):
            cleaned[key] = [
                validate_ai_context(v) if isinstance(v, dict) else v for v in value
            ]
        else:
            cleaned[key] = value
    return cleaned


def sanitize_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    try:
        return validate_ai_context(payload)
    except ValueError:
        return {k: v for k, v in payload.items() if str(k).lower() not in FORBIDDEN_KEYS}
