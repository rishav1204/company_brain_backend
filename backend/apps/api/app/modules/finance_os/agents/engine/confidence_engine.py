from __future__ import annotations

from app.modules.finance_os.agents.schemas.agents_schema import AgentContext, ConfidenceResult


def score(context: AgentContext, plan_metadata: dict | None = None) -> ConfidenceResult:
    meta = plan_metadata or {}
    data_quality = float(context.data_quality_score or meta.get("data_quality", 0.5))
    memory_hits = min(1.0, len(context.memory_snippets) / 5.0)
    graph_evidence = min(1.0, len(context.graph_paths) / 3.0)
    policy_penalty = 0.15 * len(context.policy_flags)

    raw = (
        0.30 * data_quality
        + 0.25 * memory_hits
        + 0.25 * graph_evidence
        + 0.20 * max(0.0, 1.0 - policy_penalty)
    )
    score_value = round(max(0.0, min(1.0, raw)) * 100, 2)

    if score_value >= 95:
        band = "very_strong"
    elif score_value >= 80:
        band = "strong"
    elif score_value >= 60:
        band = "review"
    else:
        band = "manual"

    amount = float(context.raw_payload.get("amount") or 0)
    vendor_risk = str(context.raw_payload.get("vendor_risk") or "").lower()
    approval_required = score_value < 80 or bool(context.policy_flags) or amount >= 100000 or vendor_risk in {"high", "critical"}

    return ConfidenceResult(
        score=score_value,
        band=band,
        approval_required=approval_required,
        factors={
            "data_quality": data_quality,
            "memory_hits": memory_hits,
            "graph_evidence": graph_evidence,
            "policy_flags": context.policy_flags,
        },
    )
