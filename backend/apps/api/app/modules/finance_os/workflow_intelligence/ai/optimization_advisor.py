from __future__ import annotations

from app.modules.finance_os.workflow_intelligence.engine.optimization_engine import (
    recommend_delegation,
    recommend_stage_removal,
)


def generate_recommendations(
    *,
    stage_stats: list[dict],
    pass_through_by_stage: dict[str, float],
    rejection_by_stage: dict[str, float],
    pending_by_assignee: dict[str, int],
) -> list[dict]:
    recs: list[dict] = []
    for stage in stage_stats:
        key = str(stage.get("step_key") or "")
        ptr = pass_through_by_stage.get(key, 0.0)
        rej = rejection_by_stage.get(key, 0.0)
        avg_h = float(stage.get("avg_seconds") or 0) / 3600
        r = recommend_stage_removal(step_key=key, pass_through_rate=ptr, rejection_rate=rej, avg_hours=avg_h)
        if r:
            recs.append(r)
    for uid, cnt in pending_by_assignee.items():
        r = recommend_delegation(assignee_id=uid, pending_count=cnt, avg_wait_hours=2.0)
        if r:
            recs.append(r)
    return recs
