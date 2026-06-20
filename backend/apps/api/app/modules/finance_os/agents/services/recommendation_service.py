from __future__ import annotations

from app.modules.finance_os.agents.schemas.agents_schema import AgentPlan, ConfidenceResult
from app.modules.finance_os.agents.repositories.recommendation_repository import recommendation_repository


class RecommendationService:
    def persist(
        self,
        org_id: str,
        execution_id: str,
        plan: AgentPlan,
        confidence: ConfidenceResult,
        *,
        workflow_instance_id: str | None = None,
    ) -> dict:
        return recommendation_repository.create(
            org_id,
            execution_id=execution_id,
            recommendation_type=plan.recommendation_type,
            recommendation=plan.recommendation,
            confidence_score=confidence.score,
            confidence_band=confidence.band,
            approval_required=confidence.approval_required,
            workflow_instance_id=workflow_instance_id,
            metadata={"plan": plan.metadata, "actions": plan.proposed_actions},
        )


recommendation_service = RecommendationService()
