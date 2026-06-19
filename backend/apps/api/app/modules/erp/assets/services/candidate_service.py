from __future__ import annotations

from app.modules.erp.assets.ai.asset_classifier import classify_asset
from app.modules.erp.assets.ai.useful_life_recommender import recommend_useful_life
from app.modules.erp.assets.events.asset_events import emit_candidate_detected
from app.modules.erp.assets.repositories.candidate_repository import candidate_repository
from app.modules.erp.assets.repositories.category_repository import category_repository, policy_repository
from app.modules.erp.assets.services.asset_service import asset_service


class CandidateService:
    def _threshold(self, org_id: str) -> float:
        policy = policy_repository.get_active(org_id) or {}
        return float(policy.get("capitalization_threshold") or 50000)

    def create_from_ap_invoice(self, org_id: str, *, invoice_id: str, amount: float, description: str | None = None) -> dict | None:
        if amount < self._threshold(org_id):
            return None
        hints = classify_asset(description or "")
        cat_id = None
        for cat in category_repository.list_active(org_id):
            if str(cat.get("category_code", "")).lower() == hints.get("category_code", "").lower():
                cat_id = cat.get("id")
                break
        candidate = candidate_repository.create(
            org_id,
            source_type="ap_invoice",
            source_id=invoice_id,
            amount=amount,
            description=description,
            suggested_category_id=cat_id,
            status="pending_reclass",
            metadata={"ai": hints, "useful_life_months": recommend_useful_life(hints)},
        )
        emit_candidate_detected(org_id, candidate_id=str(candidate["id"]), source_type="ap_invoice", source_id=invoice_id)
        return candidate

    def create_from_expense_claim(self, org_id: str, *, claim_id: str, amount: float, description: str | None = None) -> dict | None:
        if amount < self._threshold(org_id):
            return None
        hints = classify_asset(description or "")
        candidate = candidate_repository.create(
            org_id,
            source_type="expense_claim",
            source_id=claim_id,
            amount=amount,
            description=description,
            metadata={"ai": hints},
        )
        emit_candidate_detected(org_id, candidate_id=str(candidate["id"]), source_type="expense_claim", source_id=claim_id)
        return candidate

    def list(self, org_id: str, *, status: str | None = None) -> list[dict]:
        return candidate_repository.list(org_id, status=status)

    def convert(self, org_id: str, *, candidate_id: str, actor_id: str, asset_name: str | None = None) -> dict:
        candidate = candidate_repository.get(org_id, candidate_id=candidate_id)
        if not candidate:
            raise ValueError("Candidate not found")
        if str(candidate.get("status")) == "converted":
            raise ValueError("Candidate already converted")
        meta = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
        ai = meta.get("ai") if isinstance(meta.get("ai"), dict) else {}
        asset = asset_service.create(
            org_id,
            asset_name=asset_name or str(candidate.get("description") or "Capitalized asset"),
            asset_category_id=candidate.get("suggested_category_id"),
            cost=float(candidate.get("amount") or 0),
            useful_life_months=int(meta.get("useful_life_months") or ai.get("useful_life_months") or 36),
            created_by=actor_id,
            source_type=str(candidate.get("source_type")),
            source_id=str(candidate.get("source_id")),
            ap_invoice_id=str(candidate.get("source_id")) if candidate.get("source_type") == "ap_invoice" else None,
        )
        candidate_repository.set_converted(org_id, candidate_id=candidate_id, asset_id=str(asset["id"]))
        return asset


candidate_service = CandidateService()
