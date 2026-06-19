from __future__ import annotations

from datetime import date

from app.modules.erp.assets.engine.asset_lifecycle_engine import ensure_disposable
from app.modules.erp.assets.engine.disposal_engine import build_disposal_lines, compute_gain_loss
from app.modules.erp.assets.events.asset_events import emit_asset_disposed
from app.modules.erp.assets.repositories.asset_repository import asset_repository, disposal_repository
from app.modules.erp.assets.validators.capitalization_validator import validate_disposal
from app.modules.erp.journals.services.approval_service import approval_service as journal_approval_service
from app.modules.erp.journals.services.journal_service import journal_service
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator


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
        journal = journal_service.create_draft(
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
        journal_approval_service.approve(org_id, journal_id=jid, approver_id=actor_id, skip_maker_checker=True)
        if auto_post:
            posting_orchestrator.post_journal(org_id, journal_id=jid, posted_by=actor_id)

        disposal = disposal_repository.create(
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
        asset_repository.set_status(org_id, asset_id=asset_id, status="disposed", book_value=0)
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
