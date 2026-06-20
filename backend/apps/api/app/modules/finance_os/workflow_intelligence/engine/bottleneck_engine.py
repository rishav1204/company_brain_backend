from __future__ import annotations

from typing import Any


def rank_bottlenecks(stage_stats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not stage_stats:
        return []
    p95_values = [float(s.get("p95_seconds") or 0) for s in stage_stats if s.get("p95_seconds")]
    median_p95 = sorted(p95_values)[len(p95_values) // 2] if p95_values else 0
    ranked: list[dict[str, Any]] = []
    for s in stage_stats:
        p95 = float(s.get("p95_seconds") or 0)
        avg = float(s.get("avg_seconds") or 0)
        is_bottleneck = p95 > max(median_p95 * 2, 1) or (ranked and p95 == max(p95_values))
        ranked.append(
            {
                "step_key": s.get("step_key"),
                "stage_name": s.get("stage_name"),
                "avg_seconds": avg,
                "p95_seconds": p95,
                "sample_count": int(s.get("sample_count") or 0),
                "is_bottleneck": is_bottleneck or (p95 == max(p95_values) if p95_values else False),
                "rank_score": p95,
            }
        )
    ranked.sort(key=lambda x: x["rank_score"], reverse=True)
    if ranked:
        ranked[0]["is_bottleneck"] = True
    return ranked


def top_bottleneck(stage_stats: list[dict[str, Any]]) -> dict[str, Any] | None:
    ranked = rank_bottlenecks(stage_stats)
    return ranked[0] if ranked else None
