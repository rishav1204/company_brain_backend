from __future__ import annotations

from app.modules.finance_os.workflow_intelligence.engine.bottleneck_engine import rank_bottlenecks, top_bottleneck


def detect_bottlenecks(stage_stats: list[dict]) -> list[dict]:
    return rank_bottlenecks(stage_stats)


def explain_bottleneck(stage_stats: list[dict]) -> str:
    top = top_bottleneck(stage_stats)
    if not top:
        return "No bottleneck data available."
    return (
        f"Bottleneck stage: {top.get('stage_name') or top.get('step_key')} "
        f"(p95 {top.get('p95_seconds', 0):.0f}s, avg {top.get('avg_seconds', 0):.0f}s)"
    )
