from __future__ import annotations

from datetime import date

from app.modules.erp.assets.engine.asset_lifecycle_engine import ensure_depreciable, next_status_after_depreciation
from app.modules.erp.assets.engine.depreciation_engine import compute_depreciation, period_key_from_date
from app.modules.erp.assets.engine.disposal_engine import build_depreciation_lines
from app.modules.erp.assets.events.asset_events import emit_asset_depreciated
from app.modules.erp.assets.repositories.asset_repository import asset_repository
from app.modules.erp.assets.repositories.depreciation_repository import depreciation_repository
from app.modules.erp.journals.services.journal_draft_conn import approve_with_conn, create_draft_with_conn
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.services.db import get_db_conn, set_rls_org


class DepreciationService:
    def depreciate_asset(
        self,
        org_id: str,
        *,
        asset_id: str,
        depreciation_date: str | None = None,
        actor_id: str = "system",
        auto_post: bool = True,
    ) -> dict | None:
        asset = asset_repository.get(org_id, asset_id=asset_id)
        if not asset:
            raise ValueError("Asset not found")
        ensure_depreciable(str(asset.get("status")))
        dep_date = str(depreciation_date or date.today().isoformat())[:10]
        period_key = period_key_from_date(dep_date)
        if depreciation_repository.exists_for_period(org_id, asset_id=asset_id, period_key=period_key):
            return None

        cost = float(asset.get("cost") or 0)
        salvage = float(asset.get("salvage_value") or 0)
        accum = float(asset.get("accumulated_depreciation") or 0)
        book = float(asset.get("book_value") or cost)
        amount = compute_depreciation(
            cost=cost,
            salvage_value=salvage,
            useful_life_months=int(asset.get("useful_life_months") or 36),
            accumulated_depreciation=accum,
            book_value=book,
            method=str(asset.get("depreciation_method") or "straight_line"),
        )
        if amount <= 0:
            return None

        from app.modules.erp.fiscal.services.posting_guard import ensure_posting_allowed

        ensure_posting_allowed(org_id, dep_date)

        lines = build_depreciation_lines(
            org_id,
            amount=amount,
            depreciation_expense_account_id=asset.get("depreciation_expense_account_id"),
            accumulated_depreciation_account_id=asset.get("accumulated_depreciation_account_id"),
        )

        closing = round(book - amount, 2)
        new_accum = round(accum + amount, 2)
        new_status = next_status_after_depreciation(book_value=closing, salvage_value=salvage) or str(asset.get("status"))

        journal = None
        post_result = None
        jid = None

        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            journal = create_draft_with_conn(
                conn,
                org_id,
                created_by=actor_id,
                journal_type="depreciation",
                posting_date=dep_date,
                description=f"Depreciation {asset.get('asset_code')} {period_key}",
                source_type="asset_depreciation",
                source_id=asset_id,
                company_id=asset.get("company_id"),
                lines=lines,
                idempotency_key=f"asset-depr:{asset_id}:{period_key}",
            )
            jid = str(journal["journal"]["id"])
            approve_with_conn(conn, org_id, journal_id=jid, approver_id=actor_id, skip_maker_checker=True)
            if auto_post:
                post_result = posting_orchestrator.post_journal_with_conn(
                    conn, org_id, journal_id=jid, posted_by=actor_id, defer_side_effects=True
                )

            depreciation_repository.create_conn(
                conn,
                org_id,
                asset_id=asset_id,
                depreciation_date=dep_date,
                period_key=period_key,
                opening_book_value=book,
                depreciation_amount=amount,
                closing_book_value=closing,
                journal_id=jid,
            )
            asset_repository.set_status_conn(
                conn,
                org_id,
                asset_id=asset_id,
                status=new_status,
                book_value=closing,
                accumulated_depreciation=new_accum,
            )

        if auto_post and journal:
            posting_orchestrator._emit_post_side_effects(
                org_id,
                journal_id=jid,
                journal=journal["journal"],
                batch_id=str((post_result or {}).get("ledger_batch_id") or ""),
                posted_by=actor_id,
            )

        emit_asset_depreciated(org_id, asset_id=asset_id, amount=amount, period_key=period_key)
        return {"asset_id": asset_id, "depreciation_amount": amount, "journal_id": jid, "period_key": period_key}

    def run_due(self, org_id: str, *, as_of_date: str | None = None) -> list[dict]:
        dep_date = str(as_of_date or date.today().isoformat())[:10]
        results: list[dict] = []
        for asset in asset_repository.list_depreciable(org_id):
            try:
                row = self.depreciate_asset(org_id, asset_id=str(asset["id"]), depreciation_date=dep_date)
                if row:
                    results.append(row)
            except Exception:
                continue
        return results


depreciation_service = DepreciationService()
