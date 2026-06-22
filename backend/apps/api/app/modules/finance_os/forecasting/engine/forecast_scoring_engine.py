from __future__ import annotations


def score_confidence(*, data_quality: float, memory_hits: int, graph_evidence: int, history_days: int) -> tuple[float, str]:
    dq = max(0.0, min(1.0, float(data_quality or 0.0)))
    mem = max(0.0, min(1.0, float(memory_hits) / 5.0))
    graph = max(0.0, min(1.0, float(graph_evidence) / 3.0))
    hist = max(0.0, min(1.0, float(history_days) / 90.0))
    raw = 0.40 * dq + 0.20 * mem + 0.20 * graph + 0.20 * hist
    score = round(max(0.0, min(1.0, raw)) * 100.0, 2)
    if score >= 90:
        band = "high"
    elif score >= 70:
        band = "medium"
    else:
        band = "low"
    return score, band

