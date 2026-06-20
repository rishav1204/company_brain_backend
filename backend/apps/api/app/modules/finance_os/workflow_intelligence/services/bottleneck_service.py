from __future__ import annotations

from app.modules.finance_os.workflow_intelligence.ai.bottleneck_detector import detect_bottlenecks, explain_bottleneck
from app.modules.finance_os.workflow_intelligence.repositories.stage_metric_repository import stage_metric_repository


class BottleneckService:
    def list_bottlenecks(self, org_id: str, *, workflow_type: str | None = None, days: int = 30) -> list[dict]:
        stats = stage_metric_repository.aggregate_by_step(org_id, workflow_type=workflow_type, days=days)
        return detect_bottlenecks(stats)

    def explain(self, org_id: str, *, workflow_type: str | None = None) -> str:
        stats = stage_metric_repository.aggregate_by_step(org_id, workflow_type=workflow_type)
        return explain_bottleneck(stats)


bottleneck_service = BottleneckService()
