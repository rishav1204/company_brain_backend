from __future__ import annotations

import uuid

from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker
from app.modules.erp.accounts_receivable.engine.account_resolver import resolve_receivable_account
from app.modules.erp.accounts_receivable.engine.collection_engine import build_receipt_journal_lines
from app.modules.erp.accounts_receivable.events.ar_events import emit_payment_received
from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository
from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
from app.modules.erp.accounts_receivable.repositories.receipt_repository import receipt_repository
from app.modules.erp.accounts_receivable.services.ar_realtime_service import ar_realtime_service
from app.modules.erp.accounts_receivable.services.customer_balance_service import customer_balance_service
from app.modules.erp.accounts_receivable.validators.receipt_validator import receipt_validator
from app.modules.erp.journals.services.approval_service import approval_service as journal_approval_service
from app.modules.erp.journals.services.journal_service import journal_service
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator


class CollectionService:
    def _receipt_number(self) -> str:
        return "RCT-" + uuid.uuid4().hex[:10].upper()

    def record_receipt(
        self,
        org_id: str,
        *,
        customer_id: str,
        receipt_date: str,
        amount: float,
        payment_mode: str,
        bank_account_id: str,
        invoice_allocations: list[dict],
        company_id: str | None = None,
        created_by: str | None = None,
    ) -> dict:
        customer = customer_repository.get(org_id, customer_id=customer_id)
        if not customer:
            raise ValueError("Customer not found")
        receipt_validator.validate_mode(payment_mode)
        if amount <= 0:
            raise ValueError("Receipt amount must be positive")

        receipt = receipt_repository.create(
            org_id,
            customer_id=customer_id,
            receipt_number=self._receipt_number(),
            receipt_date=receipt_date,
            amount=amount,
            payment_mode=payment_mode,
            bank_account_id=bank_account_id,
            company_id=company_id,
            created_by=created_by,
            metadata={"allocations": invoice_allocations},
        )
        rid = str(receipt["id"])
        for alloc in invoice_allocations:
            receipt_repository.add_allocation(
                org_id, receipt_id=rid, invoice_id=str(alloc["invoice_id"]), amount=float(alloc["amount"])
            )
        self._audit(org_id, receipt_id=rid, action="ar.receipt.recorded", actor_id=created_by)
        return receipt

    def complete_receipt(self, org_id: str, *, receipt_id: str, completed_by: str, auto_post: bool = True) -> dict:
        receipt = receipt_repository.get(org_id, receipt_id=receipt_id)
        if not receipt:
            raise ValueError("Receipt not found")
        receipt_validator.ensure_completable(str(receipt.get("status")))

        try:
            enforce_maker_checker(
                created_by=str(receipt.get("created_by") or ""),
                actor_user_id=completed_by,
                org_id=org_id,
            )
        except MakerCheckerViolation as exc:
            raise ValueError(str(exc)) from exc

        customer = customer_repository.get(org_id, customer_id=str(receipt["customer_id"])) or {}
        receivable_id = resolve_receivable_account(org_id, customer)
        bank_id = str(receipt.get("bank_account_id") or "")
        if not receivable_id or not bank_id:
            raise ValueError("Receivable and bank accounts required")

        amount = float(receipt.get("amount") or 0)
        receipt_repository.set_status(org_id, receipt_id=receipt_id, status="processing")
        try:
            journal_lines = build_receipt_journal_lines(
                bank_account_id=bank_id, receivable_account_id=receivable_id, amount=amount
            )
            journal = journal_service.create_draft(
                org_id,
                created_by=None,
                journal_type="receipt",
                posting_date=str(receipt.get("receipt_date")),
                description=f"Receipt {receipt.get('receipt_number')}",
                source_type="ar_receipt",
                source_id=receipt_id,
                company_id=receipt.get("company_id"),
                lines=journal_lines,
                idempotency_key=f"ar-receipt:{receipt_id}",
            )
            jid = str(journal["journal"]["id"])
            journal_approval_service.approve(org_id, journal_id=jid, approver_id=completed_by, skip_maker_checker=True)
            post_result = None
            if auto_post:
                post_result = posting_orchestrator.post_journal(org_id, journal_id=jid, posted_by=completed_by)

            receipt_repository.set_status(org_id, receipt_id=receipt_id, status="completed", journal_id=jid)
            meta = receipt.get("metadata") if isinstance(receipt.get("metadata"), dict) else {}
            for alloc in meta.get("allocations") or []:
                ar_invoice_repository.record_receipt(
                    org_id, invoice_id=str(alloc["invoice_id"]), amount=float(alloc["amount"])
                )
            customer_balance_service.refresh_customer(org_id, customer_id=str(receipt["customer_id"]))
            emit_payment_received(org_id, receipt_id=receipt_id, amount=amount, customer_id=str(receipt["customer_id"]))
            ar_realtime_service.push_payment_received(org_id, receipt_id=receipt_id, amount=amount)
            self._audit(org_id, receipt_id=receipt_id, action="ar.receipt.completed", actor_id=completed_by)
            return {"receipt_id": receipt_id, "status": "completed", "journal_id": jid, "post_result": post_result}
        except Exception as exc:
            receipt_repository.set_status(org_id, receipt_id=receipt_id, status="failed")
            raise ValueError(f"Receipt completion failed: {exc}") from exc

    def list_receipts(self, org_id: str, *, customer_id: str | None = None) -> list[dict]:
        return receipt_repository.list(org_id, customer_id=customer_id)

    def _audit(self, org_id: str, *, receipt_id: str, action: str, actor_id: str | None) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=actor_id or "erp.ar",
                action=action,
                object_ref=f"erp:ar_receipt:{receipt_id}",
                entity_type="ar_receipt",
                entity_id=receipt_id,
                source_service="erp.ar",
            )
        except Exception:
            pass


collection_service = CollectionService()
