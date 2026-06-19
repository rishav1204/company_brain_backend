from __future__ import annotations

from datetime import datetime, timezone

from app.modules.erp.procurement.repositories.policy_repository import policy_repository
from app.modules.erp.procurement.workflows.pr_approval_workflow import workflow_metadata_for_amount


class ApprovalService:
    def resolve_chain(self, org_id: str, *, amount: float) -> list[str]:
        policy = policy_repository.get_active(org_id) or {}
        thresholds = policy.get("approval_thresholds")
        if isinstance(thresholds, list):
            return workflow_metadata_for_amount(amount, thresholds=thresholds)["approval_chain"]
        return workflow_metadata_for_amount(amount)["approval_chain"]

    def build_pr_metadata(self, org_id: str, *, pr_id: str, amount: float) -> dict:
        return {
            "pr_id": pr_id,
            "amount": amount,
            **workflow_metadata_for_amount(
                amount,
                thresholds=(policy_repository.get_active(org_id) or {}).get("approval_thresholds"),
            ),
        }


approval_service = ApprovalService()
