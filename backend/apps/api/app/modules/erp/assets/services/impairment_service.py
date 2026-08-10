from __future__ import annotations

from datetime import date

from app.modules.erp.assets.engine.asset_lifecycle_engine import ensure_impairable
from app.modules.erp.assets.engine.disposal_engine import build_impairment_lines
from app.modules.erp.assets.events.asset_events import emit_asset_impaired
from app.modules.erp.assets.repositories.asset_repository import asset_repository, impairment_repository
from app.modules.erp.assets.validators.capitalization_validator import validate_impairment
from app.modules.erp.journals.services.journal_draft_conn import approve_with_conn, create_draft_with_conn
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.services.db import get_db_conn, set_rls_org


class ImpairmentService:
    def impair(
        self,
        org_id: str,
        *,
        asset_id: str,
        impairment_amount: float,
        impairment_date: str | None = None,
        reason: str | None = None,
        actor_id: str,
        skip_workflow_check: bool = False,
        auto_post: bool = True,
    ) -> dict:
        asset = asset_repository.get(org_id, asset_id=asset_id)
        if not asset:
            raise ValueError("Asset not found")
        ensure_impairable(str(asset.get("status")))
        if not skip_workflow_check and not asset.get("workflow_approved"):
            raise ValueError("Asset impairment workflow approval required")

        book = float(asset.get("book_value") or 0)
        validate_impairment(impairment_amount=impairment_amount, book_value=book)
        idate = str(impairment_date or date.today().isoformat())[:10]

        from app.modules.erp.fiscal.services.posting_guard import ensure_posting_allowed

        ensure_posting_allowed(org_id, idate)

        lines = build_impairment_lines(
            org_id,
            impairment_amount=impairment_amount,
            fixed_asset_account_id=asset.get("fixed_asset_account_id"),
        )

        book_after = round(book - impairment_amount, 2)
        impair_amt = float(asset.get("impairment_amount") or 0) + impairment_amount

        journal = None
        post_result = None
        jid = None
        record = None

        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            journal = create_draft_with_conn(
                conn,
                org_id,
                created_by=actor_id,
                journal_type="adjustment",
                posting_date=idate,
                description=f"Impair asset {asset.get('asset_code')}",
                source_type="asset_impairment",
                source_id=asset_id,
                company_id=asset.get("company_id"),
                lines=lines,
                idempotency_key=f"asset-impair:{asset_id}:{idate}",
            )
            jid = str(journal["journal"]["id"])
            approve_with_conn(conn, org_id, journal_id=jid, approver_id=actor_id, skip_maker_checker=True)
            if auto_post:
                post_result = posting_orchestrator.post_journal_with_conn(
                    conn, org_id, journal_id=jid, posted_by=actor_id, defer_side_effects=True
                )

            record = impairment_repository.create_conn(
                conn,
                org_id,
                asset_id=asset_id,
                impairment_date=idate,
                impairment_amount=impairment_amount,
                book_value_before=book,
                book_value_after=book_after,
                journal_id=jid,
                reason=reason,
                created_by=actor_id,
            )
            asset_repository.set_status_conn(
                conn,
                org_id,
                asset_id=asset_id,
                status="impaired",
                book_value=book_after,
                impairment_amount=impair_amt,
            )

        if auto_post and journal:
            posting_orchestrator._emit_post_side_effects(
                org_id,
                journal_id=jid,
                journal=journal["journal"],
                batch_id=str((post_result or {}).get("ledger_batch_id") or ""),
                posted_by=actor_id,
            )

        emit_asset_impaired(org_id, asset_id=asset_id, impairment_amount=impairment_amount)
        return record

    def submit(self, org_id: str, *, asset_id: str, actor_id: str, impairment_amount: float) -> dict:
        asset = asset_repository.get(org_id, asset_id=asset_id)
        if not asset:
            raise ValueError("Asset not found")
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "asset_impairment",
                    "entity_id": asset_id,
                    "amount": impairment_amount,
                    "started_by": actor_id,
                    "metadata": {"asset_id": asset_id, "impairment_amount": impairment_amount},
                },
            )
        except Exception:
            pass
        return asset


impairment_service = ImpairmentService()
