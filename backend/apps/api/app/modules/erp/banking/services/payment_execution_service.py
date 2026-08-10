from __future__ import annotations

import re
import uuid
from datetime import date

from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker
from app.modules.erp.banking.engine.payment_engine import build_generic_payment_lines, build_internal_transfer_lines
from app.modules.erp.banking.engine.payment_policy_engine import evaluate_payment_policy
from app.modules.erp.banking.events.banking_events import emit_payment_executed, emit_payment_failed
from app.modules.erp.banking.repositories.payment_request_repository import payment_request_repository
from app.modules.erp.banking.services.bank_account_service import bank_account_service
from app.modules.erp.banking.services.bank_rail_service import bank_rail_service
from app.modules.erp.banking.services.bank_transaction_recorder import record_payment_debit, record_payment_debit_conn
from app.modules.erp.banking.services.beneficiary_service import beneficiary_service
from app.modules.erp.journals.services.journal_draft_conn import approve_with_conn, create_draft_with_conn
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.modules.erp.ports.intelligence_registry import intelligence_registry
from app.services.db import get_db_conn, set_rls_org


class PaymentExecutionService:
    def _ref(self) -> str:
        return "TPR-" + uuid.uuid4().hex[:10].upper()

    def _post_payment_journal_atomic(
        self,
        org_id: str,
        *,
        journal_type: str,
        posting_date: str,
        description: str,
        source_type: str,
        source_id: str,
        company_id: str | None,
        lines: list[dict],
        idempotency_key: str,
        executed_by: str,
        auto_post: bool,
        bank_account_id: str,
        amount: float,
        payment_reference: str,
        scheduled_date: str | None,
        beneficiary_ref: str | None,
    ) -> dict:
        post_result = None
        jid = None
        journal = None
        bank_tx = None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            journal = create_draft_with_conn(
                conn,
                org_id,
                created_by=None,
                journal_type=journal_type,
                posting_date=posting_date,
                description=description,
                source_type=source_type,
                source_id=source_id,
                company_id=company_id,
                lines=lines,
                idempotency_key=idempotency_key,
            )
            jid = str(journal["journal"]["id"])
            approve_with_conn(conn, org_id, journal_id=jid, approver_id=executed_by, skip_maker_checker=True)
            if auto_post:
                post_result = posting_orchestrator.post_journal_with_conn(
                    conn, org_id, journal_id=jid, posted_by=executed_by, defer_side_effects=True
                )
            bank_tx = record_payment_debit_conn(
                conn,
                org_id,
                bank_account_id=bank_account_id,
                amount=amount,
                reference=payment_reference,
                payment_date=(scheduled_date or "")[:10] or None,
                description=description,
                idempotency_key=f"payment:{source_id}",
                counterparty_ref=beneficiary_ref,
                source_type="payment_request",
                source_id=source_id,
            )
            conn.commit()
        if auto_post and journal:
            posting_orchestrator._emit_post_side_effects(
                org_id,
                journal_id=jid,
                journal=journal["journal"],
                batch_id=str((post_result or {}).get("ledger_batch_id") or ""),
                posted_by=executed_by,
            )
        return {"journal_id": jid, "bank_transaction_id": str(bank_tx.get("id") or "") if bank_tx else ""}

    def get_request(self, org_id: str, *, payment_request_id: str) -> dict:
        row = payment_request_repository.get(org_id, payment_request_id=payment_request_id)
        if not row:
            raise ValueError("Payment request not found")
        return row

    def create_request(self, org_id: str, *, payment_type: str, beneficiary_type: str, beneficiary_ref: str | None, bank_account_id: str, amount: float, currency_code: str, scheduled_date: str | None, source_type: str | None, source_id: str | None, company_id: str | None, created_by: str | None, metadata: dict | None = None, beneficiary_id: str | None = None, start_workflow: bool = True) -> dict:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        policy = evaluate_payment_policy(amount=amount, payment_type=payment_type, org_id=org_id, roles=None, actor_id=created_by)
        meta = dict(metadata or {})
        meta["policy"] = policy
        if beneficiary_id:
            verification = beneficiary_service.verify(org_id, beneficiary_id=beneficiary_id)
            meta["beneficiary_verification"] = verification
            meta["beneficiary_verified"] = verification.get("verified", False)
        elif payment_type == "vendor_payment" and beneficiary_ref:
            vba_id = meta.get("vendor_bank_account_id")
            if vba_id:
                verification = beneficiary_service.verify_vendor_bank(org_id, vendor_id=str(beneficiary_ref), vendor_bank_account_id=str(vba_id))
                meta["beneficiary_verification"] = verification
                meta["beneficiary_verified"] = verification.get("verified", False)
        if payment_type == "vendor_payment" and amount >= 100_000 and not meta.get("beneficiary_verified"):
            raise ValueError("Beneficiary verification required for vendor payments ≥ ₹1,00,000")
        if beneficiary_ref:
            meta["history_amounts"] = payment_request_repository.history_amounts_by_beneficiary(org_id, beneficiary_ref=str(beneficiary_ref))
            meta["new_beneficiary"] = len(meta["history_amounts"]) == 0
            if scheduled_date:
                dup = payment_request_repository.find_duplicate(org_id, beneficiary_ref=beneficiary_ref, amount=amount, scheduled_date=scheduled_date)
                if dup:
                    raise ValueError(f"Duplicate payment request: {dup.get('id')}")
        anomaly = intelligence_registry.banking().detect_payment_anomalies(amount=amount, beneficiary_ref=beneficiary_ref, history_amounts=meta.get("history_amounts") or [], beneficiary_verified=bool(meta.get("beneficiary_verified")))
        if anomaly.get("block_execution"):
            raise ValueError(f"Payment blocked: {anomaly.get('flags')}")
        meta["anomaly"] = anomaly
        req = payment_request_repository.create(org_id, payment_type=payment_type, beneficiary_type=beneficiary_type, beneficiary_ref=beneficiary_ref, bank_account_id=bank_account_id, amount=amount, currency_code=currency_code, payment_reference=self._ref(), scheduled_date=scheduled_date, source_type=source_type, source_id=source_id, company_id=company_id, created_by=created_by, metadata=meta)
        rid = str(req["id"])
        payment_request_repository.set_status(org_id, payment_request_id=rid, status="pending_approval")
        if start_workflow:
            try:
                from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created
                handle_entity_created(org_id=org_id, payload={"entity_type": "treasury_payment", "entity_id": rid, "workflow_key": "TREASURY_PAYMENT_APPROVAL", "amount": amount, "started_by": created_by, "metadata": {"payment_request_id": rid, "payment_type": payment_type, "required_roles": policy.get("required_roles")}})
            except Exception as exc:
                # INT-13: never auto-approve on workflow start failure; fail closed.
                raise ValueError(f"Treasury payment workflow initiation failed: {exc}") from exc
        return req

    def mark_workflow_approved(self, org_id: str, *, payment_request_id: str, approver_id: str) -> dict:
        row = payment_request_repository.get(org_id, payment_request_id=payment_request_id)
        if not row:
            raise ValueError("Payment request not found")
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        meta["workflow_approved"] = True
        payment_request_repository.update_metadata(org_id, payment_request_id=payment_request_id, metadata=meta)
        return payment_request_repository.set_status(org_id, payment_request_id=payment_request_id, status="approved", approval_status="approved", approved_by=approver_id)

    def cancel_request(self, org_id: str, *, payment_request_id: str, actor_id: str) -> dict:
        row = payment_request_repository.get(org_id, payment_request_id=payment_request_id)
        if not row or str(row.get("status")) not in {"draft", "pending_approval", "approved"}:
            raise ValueError("Payment request cannot be cancelled")
        return payment_request_repository.set_status(org_id, payment_request_id=payment_request_id, status="cancelled", approval_status="rejected")

    def execute_request(self, org_id: str, *, payment_request_id: str, executed_by: str, auto_post: bool = True) -> dict:
        row = payment_request_repository.get(org_id, payment_request_id=payment_request_id)
        if not row or str(row.get("status")) not in {"approved", "processing"}:
            raise ValueError("Payment request not approved for execution")
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if not meta.get("workflow_approved"):
            raise ValueError("Workflow approval required")
        try:
            enforce_maker_checker(created_by=str(row.get("created_by") or ""), actor_user_id=executed_by, org_id=org_id)
        except MakerCheckerViolation as exc:
            raise ValueError(str(exc)) from exc
        payment_type = str(row.get("payment_type"))
        amount = float(row.get("amount") or 0)
        bank_account_id = str(row["bank_account_id"])
        bank_ledger = bank_account_service.resolve_ledger_account(org_id, bank_account_id=bank_account_id)
        payment_request_repository.set_status(org_id, payment_request_id=payment_request_id, status="processing")
        try:
            rail_result = bank_rail_service.execute_payment(org_id, bank_account_id=bank_account_id, amount=amount, reference=str(row.get("payment_reference") or payment_request_id), beneficiary_ref=str(row.get("beneficiary_ref") or ""), metadata=meta)
            meta["rail_result"] = rail_result
            ap_payment_id = meta.get("ap_payment_id")
            if payment_type == "vendor_payment" and ap_payment_id:
                from app.modules.erp.accounts_payable.services.payment_service import payment_service
                result = payment_service.execute_payment(org_id, payment_id=str(ap_payment_id), executed_by=executed_by, payable_account_id=meta.get("payable_account_id"), skip_bank_transaction=True)
                jid = result.get("journal_id")
            elif payment_type == "internal_transfer":
                dest_ledger = bank_account_service.resolve_ledger_account(org_id, bank_account_id=str(meta.get("dest_bank_account_id") or ""))
                lines = build_internal_transfer_lines(source_bank_ledger_id=bank_ledger, dest_bank_ledger_id=dest_ledger, amount=amount)
                result = self._post_payment_journal_atomic(
                    org_id,
                    journal_type="contra",
                    posting_date=date.today().isoformat(),
                    description=f"Internal transfer {row.get('payment_reference')}",
                    source_type="banking_transfer",
                    source_id=payment_request_id,
                    company_id=row.get("company_id"),
                    lines=lines,
                    idempotency_key=f"banking-transfer:{payment_request_id}",
                    executed_by=executed_by,
                    auto_post=auto_post,
                    bank_account_id=bank_account_id,
                    amount=amount,
                    payment_reference=str(row.get("payment_reference") or payment_request_id),
                    scheduled_date=str(row.get("scheduled_date") or "")[:10] or None,
                    beneficiary_ref=str(row.get("beneficiary_ref") or ""),
                )
                jid = result.get("journal_id")
                bank_tx = {"id": result.get("bank_transaction_id")}
            else:
                expense_acct = str(meta.get("expense_account_id") or meta.get("liability_account_id") or "")
                if not expense_acct:
                    raise ValueError("Expense or liability account required")
                lines = build_generic_payment_lines(expense_or_liability_account_id=expense_acct, bank_ledger_account_id=bank_ledger, amount=amount)
                result = self._post_payment_journal_atomic(
                    org_id,
                    journal_type="payment",
                    posting_date=str(row.get("scheduled_date") or date.today().isoformat()),
                    description=f"Banking payment {row.get('payment_reference')}",
                    source_type="banking_payment",
                    source_id=payment_request_id,
                    company_id=row.get("company_id"),
                    lines=lines,
                    idempotency_key=f"banking-payment:{payment_request_id}",
                    executed_by=executed_by,
                    auto_post=auto_post,
                    bank_account_id=bank_account_id,
                    amount=amount,
                    payment_reference=str(row.get("payment_reference") or payment_request_id),
                    scheduled_date=str(row.get("scheduled_date") or "")[:10] or None,
                    beneficiary_ref=str(row.get("beneficiary_ref") or ""),
                )
                jid = result.get("journal_id")
                bank_tx = {"id": result.get("bank_transaction_id")}
            payment_request_repository.set_status(org_id, payment_request_id=payment_request_id, status="completed", journal_id=result.get("journal_id"))
            emit_payment_executed(org_id, payment_request_id=payment_request_id, amount=amount, journal_id=result.get("journal_id"), bank_transaction_id=str(bank_tx.get("id") or ""), ap_payment_id=str(ap_payment_id) if ap_payment_id else None)
            jid = str(result.get("journal_id") or "")
            if jid and payment_type == "internal_transfer":
                try:
                    from app.modules.erp.vouchers.services.voucher_projection_service import voucher_projection_service

                    voucher_projection_service.project_operational(
                        org_id,
                        voucher_type="contra",
                        reference_type="banking_transfer",
                        reference_id=payment_request_id,
                        source_module="banking",
                        journal_id=jid,
                        voucher_date=str(row.get("scheduled_date") or date.today().isoformat())[:10],
                        narration=f"Internal transfer {row.get('payment_reference')}",
                        company_id=row.get("company_id"),
                        created_by=executed_by,
                        status="posted" if auto_post else "journal_generated",
                        total_amount=amount,
                    )
                except Exception:
                    pass
            return {"payment_request_id": payment_request_id, "status": "completed", "bank_transaction_id": bank_tx.get("id"), "rail_result": rail_result, **result}
        except Exception as exc:
            payment_request_repository.set_status(org_id, payment_request_id=payment_request_id, status="failed")
            emit_payment_failed(org_id, payment_request_id=payment_request_id, reason=str(exc))
            raise ValueError(f"Payment execution failed: {exc}") from exc

    def create_from_ap_scheduled(self, org_id: str, *, ap_payment_id: str, bank_account_id: str, amount: float, vendor_id: str, scheduled_date: str, created_by: str | None, vendor_bank_account_id: str | None = None) -> dict:
        existing = payment_request_repository.find_by_source(org_id, source_type="ap_payment", source_id=ap_payment_id)
        if existing:
            return existing
        meta: dict = {"ap_payment_id": ap_payment_id}
        if vendor_bank_account_id:
            meta["vendor_bank_account_id"] = vendor_bank_account_id
        return self.create_request(org_id, payment_type="vendor_payment", beneficiary_type="vendor", beneficiary_ref=vendor_id, bank_account_id=bank_account_id, amount=amount, currency_code="INR", scheduled_date=scheduled_date, source_type="ap_payment", source_id=ap_payment_id, company_id=None, created_by=created_by, metadata=meta)

    def list_requests(self, org_id: str, *, status: str | None = None) -> list[dict]:
        return payment_request_repository.list(org_id, status=status)


payment_execution_service = PaymentExecutionService()
# Backward-compatible alias
banking_payment_service = payment_execution_service
treasury_payment_service = payment_execution_service
