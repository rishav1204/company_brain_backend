from __future__ import annotations

from typing import Any


def build_context(*, forecast_type: str, horizon_days: int, forecast_rows: list[dict], evidence: dict | None = None) -> str:
    evidence = evidence or {}
    head = forecast_rows[:5] if isinstance(forecast_rows, list) else []
    tail = forecast_rows[-5:] if isinstance(forecast_rows, list) and len(forecast_rows) > 5 else []
    lines: list[str] = [
        f"Forecast type: {forecast_type}",
        f"Horizon days: {horizon_days}",
        f"Rows: {len(forecast_rows) if isinstance(forecast_rows, list) else 0}",
        f"Top drivers: {', '.join(str(x) for x in (evidence.get('drivers') or [])[:5])}",
        "Head (first 5):",
        *(str(r) for r in head),
        "Tail (last 5):",
        *(str(r) for r in tail),
    ]
    return "\n".join(lines)

