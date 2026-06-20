from __future__ import annotations

from app.modules.finance_os.memory.engine.importance_engine import compute_importance


def extract(event_type: str, payload: dict) -> dict | None:
    wf_type = payload.get("workflow_type") or payload.get("workflowType") or "workflow"
    if event_type in {"approval.completed", "workflow.approved", "approval.rejected"}:
        rejection = event_type == "approval.rejected"
        reason = payload.get("reason") or payload.get("rejection_reason") or ""
        hours = payload.get("approval_hours") or payload.get("duration_hours")
        content = f"{wf_type} approval {'rejected' if rejection else 'completed'}"
        if hours:
            content += f" in {hours}h average"
        if reason:
            content += f"; reason: {reason}"
        return {
            "memory_type": "approval",
            "entity_type": "workflow_type",
            "entity_id": None,
            "title": f"{wf_type} approval pattern",
            "content": content,
            "importance_score": compute_importance(event_type=event_type, rejection=rejection),
            "references": [{"source_type": "workflow", "source_id": payload.get("workflow_id")}],
            "ttl_policy": "180d",
            "metadata": {"workflow_type": wf_type},
        }
    if event_type == "workflow.intelligence.completed":
        bottleneck = payload.get("top_bottleneck") or payload.get("bottleneck_stage")
        if not bottleneck:
            return None
        return {
            "memory_type": "approval",
            "entity_type": "workflow_type",
            "entity_id": None,
            "title": f"{wf_type} bottleneck pattern",
            "content": f"Recurring bottleneck at {bottleneck} for {wf_type}",
            "importance_score": compute_importance(event_type=event_type, base_score=75),
            "references": [{"source_type": "workflow_intelligence", "source_id": payload.get("analysis_id")}],
            "ttl_policy": "180d",
            "metadata": {"workflow_type": wf_type, "bottleneck": bottleneck},
        }
    return None
