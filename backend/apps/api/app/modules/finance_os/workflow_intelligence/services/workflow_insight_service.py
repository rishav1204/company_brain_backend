from __future__ import annotations

from app.modules.finance_os.workflow_intelligence.engine.workflow_scoring_engine import health_band, org_health_score
from app.modules.finance_os.workflow_intelligence.repositories.snapshot_repository import snapshot_repository
from app.modules.finance_os.workflow_intelligence.services.approval_optimization_service import approval_optimization_service
from app.modules.finance_os.workflow_intelligence.services.sla_prediction_service import sla_prediction_service


class WorkflowInsightService:
    def health(self, org_id: str) -> dict:
        snapshots = snapshot_repository.list_recent(org_id, limit=100)
        scores = [float(s.get("efficiency_score") or 0) for s in snapshots]
        risks = sla_prediction_service.list_risks(org_id, limit=20)
        high_risks = [r for r in risks if str(r.get("predicted_value")) == "high"]
        overload = approval_optimization_service.queue_overload(org_id)
        score = org_health_score(
            efficiency_scores=scores,
            breach_risk_count=len(high_risks),
            overload_count=len(overload),
        )
        return {
            "health_score": score,
            "health_band": health_band(score),
            "snapshot_count": len(snapshots),
            "sla_high_risk_count": len(high_risks),
            "overload_count": len(overload),
        }


workflow_insight_service = WorkflowInsightService()
