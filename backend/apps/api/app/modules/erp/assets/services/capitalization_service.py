from __future__ import annotations

from datetime import datetime, timezone

from app.modules.erp.assets.engine.account_resolver import (
    resolve_accumulated_depreciation_account,
    resolve_capitalization_credit_account,
    resolve_depreciation_expense_account,
    resolve_fixed_asset_account,
)
from app.modules.erp.assets.engine.asset_lifecycle_engine import ensure_capitalizable
from app.modules.erp.assets.engine.disposal_engine import build_capitalization_lines
from app.modules.erp.assets.events.asset_events import emit_asset_capitalized
from app.modules.erp.assets.repositories.asset_repository import asset_repository
from app.modules.erp.assets.repositories.category_repository import category_repository, policy_repository
from app.modules.erp.assets.validators.capitalization_validator import validate_capitalization
from app.modules.erp.journals.services.journal_draft_conn import approve_with_conn, create_draft_with_conn
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.services.db import get_db_conn, set_rls_org


class CapitalizationService:
    def capitalize(
        self,
        org_id: str,
        *,
        asset_id: str,
        approver_id: str,
        skip_workflow_check: bool = False,
        auto_post: bool = True,
        reclass_from_expense: bool = False,
        credit_account_id: str | None = None,
    ) -> dict:
        asset = asset_repository.get(org_id, asset_id=asset_id)
        if not asset:
            raise ValueError("Asset not found")
        ensure_capitalizable(str(asset.get("status")))
        if not skip_workflow_check and not asset.get("workflow_approved"):
            raise ValueError("Asset capitalization workflow approval required")

        policy = policy_repository.get_active(org_id) or {}
        threshold = float(policy.get("capitalization_threshold") or 50000)
        cost = float(asset.get("cost") or 0)
        validate_capitalization(
            cost=cost,
            useful_life_months=int(asset.get("useful_life_months") or 36),
            threshold=threshold,
        )

        from app.modules.erp.fiscal.services.posting_guard import ensure_posting_allowed

        posting_date = str(asset.get("purchase_date") or datetime.now(timezone.utc).date().isoformat())[:10]
        ensure_posting_allowed(org_id, posting_date)

        credit_id = credit_account_id or resolve_capitalization_credit_account(org_id, reclass_from_expense=reclass_from_expense)
        if not credit_id:
            raise ValueError("Credit account required for capitalization")

        lines = build_capitalization_lines(
            org_id,
            cost=cost,
            fixed_asset_account_id=asset.get("fixed_asset_account_id"),
            credit_account_id=credit_id,
        )

        journal = None
        post_result = None
        jid = None
        updated = None

        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            journal = create_draft_with_conn(
                conn,
                org_id,
                created_by=approver_id,
                journal_type="adjustment",
                posting_date=posting_date,
                description=f"Capitalize asset {asset.get('asset_code')}",
                source_type="asset_capitalization",
                source_id=asset_id,
                company_id=asset.get("company_id"),
                lines=lines,
                idempotency_key=f"asset-cap:{asset_id}",
            )
            jid = str(journal["journal"]["id"])
            approve_with_conn(conn, org_id, journal_id=jid, approver_id=approver_id, skip_maker_checker=True)
            if auto_post:
                post_result = posting_orchestrator.post_journal_with_conn(
                    conn, org_id, journal_id=jid, posted_by=approver_id, defer_side_effects=True
                )

            updated = asset_repository.set_status_conn(
                conn,
                org_id,
                asset_id=asset_id,
                status="active",
                capitalization_journal_id=jid,
                capitalization_date=posting_date,
                approved_by=approver_id,
                book_value=cost,
                workflow_approved=True,
            )

        if auto_post and journal:
            posting_orchestrator._emit_post_side_effects(
                org_id,
                journal_id=jid,
                journal=journal["journal"],
                batch_id=str((post_result or {}).get("ledger_batch_id") or ""),
                posted_by=approver_id,
            )

        emit_asset_capitalized(org_id, asset_id=asset_id, journal_id=jid)
        return updated


capitalization_service = CapitalizationService()


def apply_category_defaults(org_id: str, *, category_id: str | None) -> dict:
    if not category_id:
        return {}
    cat = category_repository.get(org_id, category_id=category_id)
    if not cat:
        return {}
    cost = 0.0
    salvage_pct = float(cat.get("default_salvage_percent") or 0)
    return {
        "useful_life_months": int(cat.get("default_useful_life_months") or 36),
        "depreciation_method": str(cat.get("depreciation_method") or "straight_line"),
        "salvage_value": round(cost * salvage_pct / 100, 2),
        "fixed_asset_account_id": resolve_fixed_asset_account(org_id),
        "accumulated_depreciation_account_id": resolve_accumulated_depreciation_account(org_id),
        "depreciation_expense_account_id": resolve_depreciation_expense_account(org_id),
    }
