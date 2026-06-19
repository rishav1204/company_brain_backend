from __future__ import annotations

from datetime import datetime, timezone

from app.modules.erp.assets.engine.account_resolver import (
    resolve_accumulated_depreciation_account,
    resolve_depreciation_expense_account,
    resolve_fixed_asset_account,
)
from app.modules.erp.assets.events.asset_events import emit_asset_created
from app.modules.erp.assets.repositories.asset_repository import asset_repository
from app.modules.erp.assets.repositories.category_repository import category_repository
from app.modules.erp.assets.services.capitalization_service import apply_category_defaults
from app.modules.erp.assets.validators.asset_validator import ensure_submittable
from app.modules.erp.assets.workflows.capitalization_workflow import workflow_metadata


class AssetService:
    def _asset_code(self) -> str:
        return f"FA-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    def _audit(self, org_id: str, *, action: str, asset_id: str, actor_id: str | None) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id, actor_id=actor_id, action=action,
                resource_type="fixed_asset", resource_id=asset_id, details={},
            )
        except Exception:
            pass

    def create(
        self,
        org_id: str,
        *,
        asset_name: str,
        asset_category_id: str | None = None,
        purchase_date: str | None = None,
        cost: float = 0,
        salvage_value: float | None = None,
        useful_life_months: int | None = None,
        company_id: str | None = None,
        location: str | None = None,
        department_id: str | None = None,
        custodian_id: str | None = None,
        cost_center_id: str | None = None,
        created_by: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        ap_invoice_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        defaults = apply_category_defaults(org_id, category_id=asset_category_id)
        if salvage_value is None and cost > 0 and asset_category_id:
            cat = category_repository.get(org_id, category_id=asset_category_id)
            if cat:
                salvage_value = round(cost * float(cat.get("default_salvage_percent") or 0) / 100, 2)
        asset = asset_repository.create(
            org_id,
            asset_code=self._asset_code(),
            asset_name=asset_name,
            asset_category_id=asset_category_id,
            purchase_date=purchase_date,
            cost=cost,
            salvage_value=float(salvage_value or 0),
            useful_life_months=int(useful_life_months or defaults.get("useful_life_months") or 36),
            depreciation_method=str(defaults.get("depreciation_method") or "straight_line"),
            company_id=company_id,
            location=location,
            department_id=department_id,
            custodian_id=custodian_id,
            cost_center_id=cost_center_id,
            fixed_asset_account_id=defaults.get("fixed_asset_account_id") or resolve_fixed_asset_account(org_id),
            accumulated_depreciation_account_id=defaults.get("accumulated_depreciation_account_id") or resolve_accumulated_depreciation_account(org_id),
            depreciation_expense_account_id=defaults.get("depreciation_expense_account_id") or resolve_depreciation_expense_account(org_id),
            source_type=source_type,
            source_id=source_id,
            ap_invoice_id=ap_invoice_id,
            created_by=created_by,
            metadata=metadata,
        )
        emit_asset_created(org_id, asset_id=str(asset["id"]), asset_code=str(asset.get("asset_code")))
        self._audit(org_id, action="asset.created", asset_id=str(asset["id"]), actor_id=created_by)
        return self.get(org_id, asset_id=str(asset["id"])) or asset

    def get(self, org_id: str, *, asset_id: str) -> dict | None:
        return asset_repository.get(org_id, asset_id=asset_id)

    def list(self, org_id: str, *, status: str | None = None, category_id: str | None = None) -> list[dict]:
        return asset_repository.list(org_id, status=status, category_id=category_id)

    def submit(self, org_id: str, *, asset_id: str, actor_id: str) -> dict:
        asset = asset_repository.get(org_id, asset_id=asset_id)
        if not asset:
            raise ValueError("Asset not found")
        ensure_submittable(str(asset.get("status")))
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "asset_capitalization",
                    "entity_id": asset_id,
                    "amount": float(asset.get("cost") or 0),
                    "started_by": actor_id,
                    "metadata": workflow_metadata(asset_id=asset_id, amount=float(asset.get("cost") or 0)),
                },
            )
        except Exception:
            pass
        self._audit(org_id, action="asset.submitted", asset_id=asset_id, actor_id=actor_id)
        return asset

    def mark_workflow_approved(self, org_id: str, *, asset_id: str) -> dict:
        return asset_repository.set_status(org_id, asset_id=asset_id, status="draft", workflow_approved=True)


asset_service = AssetService()
