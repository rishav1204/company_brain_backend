from __future__ import annotations

from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker
from app.modules.erp.banking.repositories.bank_transaction_repository import bank_transaction_repository
from app.modules.erp.reconciliation.engine.settlement_engine import group_status
from app.modules.erp.reconciliation.events.reconciliation_events import emit_reconciliation_completed
from app.modules.erp.reconciliation.repositories.match_line_repository import match_line_repository
from app.modules.erp.reconciliation.repositories.reconciliation_repository import reconciliation_repository
from app.modules.erp.reconciliation.validators.approval_validator import validate_approve_status, validate_reject_status


class ApprovalService:
    def approve(
        self,
        org_id: str,
        *,
        reconciliation_id: str,
        approved_by: str,
        ledger_entry_id: str | None = None,
        roles: list[str] | None = None,
    ) -> dict:
        row = reconciliation_repository.get(org_id, reconciliation_id=reconciliation_id)
        if not row:
            raise ValueError("Reconciliation not found")
        validate_approve_status(str(row.get("status")))

        from app.modules.erp.fiscal.services.posting_validation_service import posting_validation_service

        bank_tx = bank_transaction_repository.get(org_id, transaction_id=str(row["bank_transaction_id"]))
        posting_date = str((bank_tx or {}).get("transaction_date") or "")[:10] or None
        if posting_date:
            posting_validation_service.validate_period_open(org_id, posting_date, actor_id=approved_by, roles=roles)

        try:
            enforce_maker_checker(
                created_by=str((row.get("metadata") or {}).get("created_by") or ""),
                actor_user_id=approved_by,
                org_id=org_id,
            )
        except MakerCheckerViolation:
            pass

        lines = match_line_repository.list_for_reconciliation(org_id, reconciliation_id=reconciliation_id)
        final_status = group_status(lines) if lines else "matched"
        match_type = "partial" if final_status == "partially_matched" else "matched"

        approved = reconciliation_repository.approve(
            org_id,
            reconciliation_id=reconciliation_id,
            approved_by=approved_by,
            ledger_entry_id=ledger_entry_id or row.get("ledger_entry_id"),
            status=final_status,
            match_type=match_type,
        )
        bank_transaction_repository.set_reconciliation_status(
            org_id, transaction_id=str(approved["bank_transaction_id"]), status=final_status
        )
        emit_reconciliation_completed(
            org_id,
            reconciliation_id=reconciliation_id,
            bank_transaction_id=str(approved["bank_transaction_id"]),
            ledger_entry_id=approved.get("ledger_entry_id"),
        )
        try:
            from app.modules.erp.treasury.services.cash_position_service import cash_position_service

            cash_position_service.refresh_and_emit(org_id)
        except Exception:
            pass
        self._audit(org_id, reconciliation_id=reconciliation_id, action="reconciliation.approved", actor_id=approved_by)
        return approved

    def reject(self, org_id: str, *, reconciliation_id: str, actor_id: str) -> dict:
        row = reconciliation_repository.get(org_id, reconciliation_id=reconciliation_id)
        if not row:
            raise ValueError("Reconciliation not found")
        validate_reject_status(str(row.get("status")))
        result = reconciliation_repository.reject(org_id, reconciliation_id=reconciliation_id)
        bank_transaction_repository.set_reconciliation_status(
            org_id, transaction_id=str(row["bank_transaction_id"]), status="unreconciled"
        )
        self._audit(org_id, reconciliation_id=reconciliation_id, action="reconciliation.rejected", actor_id=actor_id)
        return result

    def _audit(self, org_id: str, *, reconciliation_id: str, action: str, actor_id: str) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=actor_id,
                action=action,
                object_ref=f"erp:reconciliation:{reconciliation_id}",
                entity_type="reconciliation",
                entity_id=reconciliation_id,
                source_service="erp.reconciliation",
            )
        except Exception:
            pass


approval_service = ApprovalService()
