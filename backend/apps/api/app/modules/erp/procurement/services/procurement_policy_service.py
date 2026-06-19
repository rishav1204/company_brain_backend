from __future__ import annotations

from app.modules.erp.procurement.repositories.policy_repository import policy_repository


class ProcurementPolicyService:
    def get_active(self, org_id: str) -> dict:
        return policy_repository.get_active(org_id) or {
            "mandatory_po": True,
            "preferred_vendors_only": False,
            "budget_enforcement": False,
            "price_tolerance_pct": 2,
            "amount_tolerance_pct": 2,
            "qty_tolerance_pct": 0,
            "approval_thresholds": [],
        }

    def list_policies(self, org_id: str) -> list[dict]:
        return policy_repository.list(org_id)

    def get_tolerances(self, org_id: str) -> dict:
        policy = self.get_active(org_id)
        return {
            "qty_tolerance_pct": float(policy.get("qty_tolerance_pct") or 0),
            "price_tolerance_pct": float(policy.get("price_tolerance_pct") or 2),
            "amount_tolerance_pct": float(policy.get("amount_tolerance_pct") or 2),
        }

    def ensure_vendor_allowed(self, org_id: str, *, vendor: dict) -> None:
        policy = self.get_active(org_id)
        if not policy.get("preferred_vendors_only"):
            return
        meta = vendor.get("metadata") if isinstance(vendor.get("metadata"), dict) else {}
        if not meta.get("preferred"):
            raise ValueError("Vendor is not on preferred vendor list")


procurement_policy_service = ProcurementPolicyService()
