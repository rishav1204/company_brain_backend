from __future__ import annotations

import json
from typing import Any


def build_reasoning_context(
    *,
    snapshot: dict | None,
    stage_metrics: list[dict],
    bottlenecks: list[dict],
    predictions: list[dict],
    recommendations: list[dict],
) -> str:
    return json.dumps(
        {
            "snapshot": snapshot,
            "stage_metrics": stage_metrics[:20],
            "bottlenecks": bottlenecks[:5],
            "predictions": predictions[:10],
            "recommendations": recommendations[:10],
        },
        default=str,
    )[:10000]
