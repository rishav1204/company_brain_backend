from __future__ import annotations

from datetime import date

from app.modules.erp.banking.repositories.bank_account_repository import bank_account_repository
from app.modules.erp.reconciliation.events.reconciliation_events import (
    emit_reconciliation_adjustment_posted,
    emit_reconciliation_adjustment_required,
)
from app.modules.erp.reconciliation.repositories.adjustment_repository import adjustment_repository
from app.modules.erp.reconciliation.validators.reconciliation_validator import validate_adjustment


class AdjustmentService:
    def create(
        self,
        org_id: str,
        *,
        bank_transaction_id: str | None,
        reconciliation_id: str | None,
        adjustment_type: str,
        amount: float,
        expense_account_id: str,
        bank_account_id: str,
        description: str | None = None,
        created_by: str | None = None,
    ) -> dict:
        validate_adjustment(
            adjustment_type=adjustment_type,
            amount=amount,
            expense_account_id=expense_account_id,
            bank_account_id=bank_account_id,
        )
        row = adjustment_repository.create(
            org_id,
            bank_transaction_id=bank_transaction_id,
            reconciliation_id=reconciliation_id,
            adjustment_type=adjustment_type,
            amount=amount,
            expense_account_id=expense_account_id,
            bank_account_id=bank_account_id,
            metadata={"description": description or "", "created_by": created_by},
        )
        emit_reconciliation_adjustment_required(
            org_id, adjustment_id=str(row["id"]), amount=amount, adjustment_type=adjustment_type
        )
        return row

    def approve_and_post(self, org_id: str, *, adjustment_id: str, approved_by: str, roles: list[str] | None = None) -> dict:
        adj = adjustment_repository.get(org_id, adjustment_id=adjustment_id)
        if not adj:
            raise ValueError("Adjustment not found")
        if str(adj.get("status")) == "posted":
            return adj

        from app.modules.erp.fiscal.services.posting_validation_service import posting_validation_service
        from app.modules.erp.journals.services.journal_service import journal_service
        from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator

        posting_date = date.today().isoformat()
        posting_validation_service.validate_period_open(org_id, posting_date, actor_id=approved_by, roles=roles)

        bank_acct = bank_account_repository.get(org_id, bank_account_id=str(adj["bank_account_id"]))
        if not bank_acct or not bank_acct.get("ledger_account_id"):
            raise ValueError("Bank account ledger link required")
        amount = float(adj["amount"])
        lines = [
            {"account_id": str(adj["expense_account_id"]), "debit_amount": amount, "credit_amount": 0, "description": adj.get("adjustment_type")},
            {"account_id": str(bank_acct["ledger_account_id"]), "debit_amount": 0, "credit_amount": amount, "description": "Bank adjustment"},
        ]
        journal = journal_service.create_draft(
            org_id,
            created_by=approved_by,
            journal_type="adjustment",
            posting_date=posting_date,
            description=f"Reconciliation adjustment {adj.get('adjustment_type')}",
            source_type="reconciliation_adjustment",
            source_id=adjustment_id,
            lines=lines,
            idempotency_key=f"recon-adj:{adjustment_id}",
        )
        jid = str(journal.get("id") or journal.get("journal_id") or "")
        if jid:
            posting_orchestrator.post_journal(org_id, journal_id=jid, posted_by=approved_by)
        result = adjustment_repository.mark_posted(org_id, adjustment_id=adjustment_id, journal_id=jid, approved_by=approved_by)
        emit_reconciliation_adjustment_posted(org_id, adjustment_id=adjustment_id, journal_id=jid)
        return result


adjustment_service = AdjustmentService()
