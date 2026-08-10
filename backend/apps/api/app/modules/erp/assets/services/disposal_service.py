from __future__ import annotations

from datetime import date

from app.modules.erp.assets.engine.asset_lifecycle_engine import ensure_disposable
from app.modules.erp.assets.engine.disposal_engine import build_disposal_lines, compute_gain_loss
from app.modules.erp.assets.events.asset_events import emit_asset_disposed
from app.modules.erp.assets.repositories.asset_repository import asset_repository, disposal_repository
from app.modules.erp.assets.validators.capitalization_validator import validate_disposal
from app.modules.erp.journals.services.journal_draft_conn import approve_with_conn, create_draft_with_conn
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.services.db import get_db_conn, set_rls_org


class DisposalService:
    def dispose(
        self,
        org_id: str,
        *,
        asset_id: str,
        sale_amount: float,
        disposal_date: str | None = None,
        bank_account_id: str | None = None,
        reason: str | None = None,
        actor_id: str,
        skip_workflow_check: bool = False,
        auto_post: bool = True,
    ) -> dict:
        asset = asset_repository.get(org_id, asset_id=asset_id)
        if not asset:
            raise ValueError("Asset not found")
        ensure_disposable(str(asset.get("status")))
        if not skip_workflow_check and not asset.get("workflow_approved"):
            raise ValueError("Asset disposal workflow approval required")
        validate_disposal(sale_amount=sale_amount)

        ddate = str(disposal_date or date.today().isoformat())[:10]
        from app.modules.erp.fiscal.services.posting_guard import ensure_posting_allowed

        ensure_posting_allowed(org_id, ddate)

        cost = float(asset.get("cost") or 0)
        accum = float(asset.get("accumulated_depreciation") or 0)
        book = float(asset.get("book_value") or 0)
        gain_loss = compute_gain_loss(sale_amount=sale_amount, book_value=book)

        lines = build_disposal_lines(
            org_id,
            cost=cost,
            accumulated_depreciation=accum,
            book_value=book,
            sale_amount=sale_amount,
            fixed_asset_account_id=asset.get("fixed_asset_account_id"),
            accumulated_depreciation_account_id=asset.get("accumulated_depreciation_account_id"),
            bank_account_id=bank_account_id,
        )

        journal = None
        post_result = None
        jid = None
        disposal = None

        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            journal = create_draft_with_conn(
                conn,
                org_id,
                created_by=actor_id,
                journal_type="adjustment",
                posting_date=ddate,
                description=f"Dispose asset {asset.get('asset_code')}",
                source_type="asset_disposal",
                source_id=asset_id,
                company_id=asset.get("company_id"),
                lines=lines,
                idempotency_key=f"asset-disposal:{asset_id}",
            )
            jid = str(journal["journal"]["id"])
            approve_with_conn(conn, org_id, journal_id=jid, approver_id=actor_id, skip_maker_checker=True)
            if auto_post:
                post_result = posting_orchestrator.post_journal_with_conn(
                    conn, org_id, journal_id=jid, posted_by=actor_id, defer_side_effects=True
                )

            disposal = disposal_repository.create_conn(
                conn,
                org_id,
                asset_id=asset_id,
                disposal_date=ddate,
                sale_amount=sale_amount,
                book_value=book,
                gain_loss=gain_loss,
                journal_id=jid,
                reason=reason,
                created_by=actor_id,
            )
            asset_repository.set_status_conn(conn, org_id, asset_id=asset_id, status="disposed", book_value=0)

        if auto_post and journal:
            posting_orchestrator._emit_post_side_effects(
                org_id,
                journal_id=jid,
                journal=journal["journal"],
                batch_id=str((post_result or {}).get("ledger_batch_id") or ""),
                posted_by=actor_id,
            )

        emit_asset_disposed(org_id, asset_id=asset_id, gain_loss=gain_loss)
        return disposal

    def submit_for_disposal(self, org_id: str, *, asset_id: str, actor_id: str, sale_amount: float) -> dict:
        asset = asset_repository.get(org_id, asset_id=asset_id)
        if not asset:
            raise ValueError("Asset not found")
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "asset_disposal",
                    "entity_id": asset_id,
                    "amount": sale_amount,
                    "started_by": actor_id,
                    "metadata": {"asset_id": asset_id, "sale_amount": sale_amount},
                },
            )
        except Exception:
            pass
        return asset_repository.set_status(org_id, asset_id=asset_id, status=str(asset.get("status")), workflow_approved=False)


disposal_service = DisposalService()
