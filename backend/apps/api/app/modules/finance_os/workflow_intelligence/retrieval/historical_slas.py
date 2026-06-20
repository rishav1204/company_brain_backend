from __future__ import annotations

from app.modules.finance_os.workflow_intelligence.repositories.stage_metric_repository import stage_metric_repository


def historical_stage_p95(org_id: str, *, workflow_type: str | None = None, days: int = 30) -> dict[str, float]:
    rows = stage_metric_repository.aggregate_by_step(org_id, workflow_type=workflow_type, days=days)
    return {str(r.get("step_key") or ""): float(r.get("p95_seconds") or 0) for r in rows if r.get("step_key")}
