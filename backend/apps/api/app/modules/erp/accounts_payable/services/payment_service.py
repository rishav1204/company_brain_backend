from __future__ import annotations

import uuid

from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker
from app.modules.erp.accounts_payable.engine.payment_engine import build_payment_journal_lines
from app.modules.erp.accounts_payable.engine.payable_engine import resolve_default_payable_account
from app.modules.erp.accounts_payable.services.ap_realtime_service import ap_realtime_service
from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
from app.modules.erp.accounts_payable.repositories.payment_repository import payment_repository
from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository
from app.modules.erp.accounts_payable.services.vendor_balance_service import vendor_balance_service
from app.modules.erp.accounts_payable.validators.payment_validator import payment_validator
from app.modules.erp.journals.services.journal_draft_conn import approve_with_conn, create_draft_with_conn
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.modules.platform.events.events.erp_events import emit_payment_completed, emit_payment_failed
from app.services.db import get_db_conn, set_rls_org
from app.services.logger import log_event


class PaymentService:
    def _payment_ref(self) -> str:
        return "PAY-" + uuid.uuid4().hex[:10].upper()

    def schedule_payment(
        self,
        org_id: str,
        *,
        vendor_id: str,
        payment_date: str,
        amount: float,
        invoice_allocations: list[dict],
        bank_account_id: str,
        created_by: str | None = None,
        company_id: str | None = None,
        branch_id: str | None = None,
    ) -> dict:
        vendor = vendor_repository.get(org_id, vendor_id=vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        existing = payment_repository.find_duplicate_schedule(
            org_id, vendor_id=vendor_id, payment_date=payment_date, amount=amount
        )
        if existing:
            raise ValueError(f"Duplicate payment schedule detected: {existing.get('id')}")

        payment = payment_repository.create(
            org_id,
            vendor_id=vendor_id,
            payment_reference=self._payment_ref(),
            payment_date=payment_date,
            amount=amount,
            bank_account_id=bank_account_id,
            company_id=company_id,
            branch_id=branch_id,
            created_by=created_by,
            metadata={"allocations": invoice_allocations, "workflow_approved": False},
        )
        pid = str(payment["id"])
        for alloc in invoice_allocations:
            payment_repository.add_allocation(
                org_id,
                payment_id=pid,
                invoice_id=str(alloc["invoice_id"]),
                amount=float(alloc["amount"]),
            )
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "payment",
                    "entity_id": pid,
                    "amount": amount,
                    "started_by": created_by,
                    "metadata": {"ap_payment_id": pid, "vendor_id": vendor_id},
                },
            )
        except Exception as exc:
            raise ValueError(f"Payment workflow initiation failed: {exc}") from exc
        ap_realtime_service.push_payment_scheduled(org_id, payment_id=pid, amount=amount)
        self._audit(org_id, payment_id=pid, action="ap.payment.scheduled", actor_id=created_by)
        return payment

    def mark_workflow_approved(self, org_id: str, *, payment_id: str) -> dict:
        payment = payment_repository.get(org_id, payment_id=payment_id)
        if not payment:
            raise ValueError("Payment not found")
        meta = payment.get("metadata") if isinstance(payment.get("metadata"), dict) else {}
        meta["workflow_approved"] = True
        return payment_repository.update_metadata(org_id, payment_id=payment_id, metadata=meta)

    def execute_payment(
        self,
        org_id: str,
        *,
        payment_id: str,
        executed_by: str,
        payable_account_id: str | None = None,
        skip_bank_transaction: bool = False,
    ) -> dict:
        from app.core.redis_lock import redis_lock

        lock_key = f"ap:payment:execute:{org_id}:{payment_id}"
        with redis_lock(lock_key, ttl_seconds=60, wait_seconds=10.0):
            return self._execute_payment_locked(
                org_id,
                payment_id=payment_id,
                executed_by=executed_by,
                payable_account_id=payable_account_id,
                skip_bank_transaction=skip_bank_transaction,
            )

    def _execute_payment_locked(
        self,
        org_id: str,
        *,
        payment_id: str,
        executed_by: str,
        payable_account_id: str | None = None,
        skip_bank_transaction: bool = False,
    ) -> dict:
        payment = payment_repository.get(org_id, payment_id=payment_id)
        if not payment:
            raise ValueError("Payment not found")
        payment_validator.ensure_executable(str(payment.get("status")))
        meta = payment.get("metadata") if isinstance(payment.get("metadata"), dict) else {}
        if not meta.get("workflow_approved"):
            raise ValueError("Payment workflow approval required before execution")

        allocations = meta.get("allocations") or []
        payment_amount = float(payment.get("amount") or 0)
        alloc_total = sum(float(alloc.get("amount") or 0) for alloc in allocations)
        if allocations and abs(alloc_total - payment_amount) > 0.01:
            raise ValueError("Payment allocation total must equal payment amount")

        for alloc in allocations:
            inv = invoice_repository.get(org_id, invoice_id=str(alloc.get("invoice_id")))
            if not inv:
                raise ValueError(f"Invoice not found: {alloc.get('invoice_id')}")
            inv_meta = inv.get("metadata") if isinstance(inv.get("metadata"), dict) else {}
            po_id = inv.get("purchase_order_id")
            if po_id:
                try:
                    from app.modules.erp.procurement.services.matching_service import matching_service

                    match = matching_service.get_for_invoice(org_id, ap_invoice_id=str(alloc.get("invoice_id")))
                    if match and str(match.get("match_status")) in {"exception", "rejected"}:
                        raise ValueError(
                            f"Three-way match failed for invoice {inv.get('id')}: status {match.get('match_status')}"
                        )
                except ValueError:
                    raise
                except Exception as exc:
                    raise ValueError(f"Procurement match check failed: {exc}") from exc

        try:
            enforce_maker_checker(
                created_by=str(payment.get("created_by") or ""),
                actor_user_id=executed_by,
                org_id=org_id,
            )
        except MakerCheckerViolation as exc:
            raise ValueError(str(exc)) from exc

        vendor = vendor_repository.get(org_id, vendor_id=str(payment["vendor_id"])) or {}
        payable_id = payable_account_id or resolve_default_payable_account(org_id, vendor)
        bank_id = str(payment.get("bank_account_id") or "")
        if bank_id:
            from app.modules.erp.treasury.services.bank_account_service import bank_account_service

            bank_id = bank_account_service.resolve_ledger_account(org_id, bank_account_id=bank_id)
        if not payable_id or not bank_id:
            raise ValueError("Payable and bank accounts required")

        amount = float(payment.get("amount") or 0)
        try:
            from app.modules.erp.tax.services.tax_account_setup_service import tax_account_setup_service
            from app.modules.erp.tax.services.tds_service import tds_service

            treasury_bank_id = str(payment.get("bank_account_id") or "")
            bank_tx_id = None
            post_result = None
            jid = None
            tds_result: dict = {}

            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                tax_account_setup_service.ensure_tax_accounts(org_id, company_id=payment.get("company_id"))
                tds_result = tds_service.deduct_with_conn(
                    conn,
                    org_id,
                    payment_id=payment_id,
                    payable_account_id=payable_id,
                    bank_account_id=bank_id,
                )
                journal_lines = tds_result.get("journal_lines") or build_payment_journal_lines(
                    payable_account_id=payable_id,
                    bank_account_id=bank_id,
                    amount=amount,
                )
                bank_payment_amount = float(tds_result.get("net_amount") or amount)
                payment_repository.set_status_conn(
                    conn, org_id, payment_id=payment_id, status="processing"
                )
                journal = create_draft_with_conn(
                    conn,
                    org_id,
                    created_by=None,
                    journal_type="payment",
                    posting_date=str(payment.get("payment_date")),
                    description=f"Payment {payment.get('payment_reference')}",
                    source_type="ap_payment",
                    source_id=payment_id,
                    company_id=payment.get("company_id"),
                    lines=journal_lines,
                    idempotency_key=f"ap-payment:{payment_id}",
                )
                jid = str(journal["journal"]["id"])
                approve_with_conn(conn, org_id, journal_id=jid, approver_id=executed_by)
                post_result = posting_orchestrator.post_journal_with_conn(
                    conn, org_id, journal_id=jid, posted_by=executed_by, defer_side_effects=True
                )
                payment_repository.set_status_conn(
                    conn, org_id, payment_id=payment_id, status="completed", journal_id=jid
                )
                for alloc in meta.get("allocations") or []:
                    invoice_repository.record_payment_conn(
                        conn,
                        org_id,
                        invoice_id=str(alloc["invoice_id"]),
                        amount=float(alloc["amount"]),
                    )
                if not skip_bank_transaction:
                    from app.modules.erp.treasury.services.bank_transaction_recorder import record_payment_debit_conn

                    bank_tx = record_payment_debit_conn(
                        conn,
                        org_id,
                        bank_account_id=treasury_bank_id,
                        amount=bank_payment_amount,
                        reference=str(payment.get("payment_reference") or payment_id),
                        payment_date=str(payment.get("payment_date") or "")[:10],
                        description=f"AP payment {payment.get('payment_reference')}",
                        idempotency_key=f"ap-payment-tx:{payment_id}",
                        counterparty_ref=str(payment.get("vendor_id") or ""),
                        source_id=payment_id,
                    )
                    bank_tx_id = bank_tx.get("id")

            posting_orchestrator._emit_post_side_effects(
                org_id,
                journal_id=jid,
                journal=journal["journal"],
                batch_id=str(post_result.get("ledger_batch_id") or ""),
                posted_by=executed_by,
            )
            vendor_balance_service.refresh_vendor(org_id, vendor_id=str(payment["vendor_id"]))
            emit_payment_completed(
                org_id, payment_id=payment_id, amount=bank_payment_amount, trace_id=None,
                journal_id=jid,
            )
            ap_realtime_service.push_payment_completed(org_id, payment_id=payment_id, amount=bank_payment_amount)
            self._audit(org_id, payment_id=payment_id, action="ap.payment.completed", actor_id=executed_by)

            try:
                from app.modules.erp.vouchers.services.voucher_projection_service import voucher_projection_service

                voucher_projection_service.project_operational(
                    org_id,
                    voucher_type="payment",
                    reference_type="ap_payment",
                    reference_id=payment_id,
                    source_module="accounts_payable",
                    journal_id=jid,
                    voucher_date=str(payment.get("payment_date")),
                    narration=f"Payment {payment.get('payment_reference')}",
                    company_id=payment.get("company_id"),
                    created_by=executed_by,
                    status="posted",
                    total_amount=amount,
                )
            except Exception as exc:
                log_event("ap.voucher_projection_failed", org_id=org_id, payment_id=payment_id, error=str(exc))

            return {
                "payment_id": payment_id,
                "status": "completed",
                "journal_id": jid,
                "post_result": post_result,
                "bank_transaction_id": bank_tx_id,
                "tds": {
                    "tds_amount": tds_result.get("tds_amount", 0),
                    "net_amount": bank_payment_amount,
                    "section_code": tds_result.get("section_code"),
                },
            }
        except Exception as exc:
            payment_repository.set_status(org_id, payment_id=payment_id, status="failed")
            emit_payment_failed(org_id, payment_id=payment_id, reason=str(exc))
            raise ValueError(f"Payment execution failed: {exc}") from exc

    def list_payments(
        self,
        org_id: str,
        *,
        status: str | None = None,
        branch_ids: list[str] | None = None,
    ) -> list[dict]:
        return payment_repository.list(org_id, status=status, branch_ids=branch_ids)

    def reverse_payment(
        self,
        org_id: str,
        *,
        payment_id: str,
        reversed_by: str,
        reason: str,
    ) -> dict:
        payment = payment_repository.get(org_id, payment_id=payment_id)
        if not payment:
            raise ValueError("Payment not found")
        if str(payment.get("status")) != "completed":
            raise ValueError("Only completed payments can be reversed")
        jid = str(payment.get("journal_id") or "")
        if not jid:
            raise ValueError("Payment has no posted journal to reverse")
        from app.modules.erp.journals.repositories.journal_repository import journal_repository
        from app.modules.erp.gl.services.reversal_service import reversal_service
        from app.modules.erp.tax.services.tds_service import tds_service

        journal = journal_repository.get(org_id, journal_id=jid) or {}
        batch_id = str(journal.get("ledger_batch_id") or "")
        if not batch_id:
            raise ValueError("Posted journal has no ledger batch for reversal")
        meta = payment.get("metadata") if isinstance(payment.get("metadata"), dict) else {}
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            reversal = reversal_service.reverse_batch_with_conn(
                conn, org_id, batch_id=batch_id, reversed_by=reversed_by
            )
            tds_service.reverse_for_payment(org_id, payment_id=payment_id, conn=conn)
            for alloc in meta.get("allocations") or []:
                invoice_repository.reverse_payment_conn(
                    conn,
                    org_id,
                    invoice_id=str(alloc.get("invoice_id")),
                    amount=float(alloc.get("amount") or 0),
                )
            payment_repository.set_status_conn(conn, org_id, payment_id=payment_id, status="reversed")
        vendor_balance_service.refresh_vendor(org_id, vendor_id=str(payment["vendor_id"]))
        self._audit(org_id, payment_id=payment_id, action="ap.payment.reversed", actor_id=reversed_by)
        return {"payment_id": payment_id, "status": "reversed", "reversal": reversal}

    def _audit(self, org_id: str, *, payment_id: str, action: str, actor_id: str | None) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=actor_id or "erp.ap",
                action=action,
                object_ref=f"erp:ap_payment:{payment_id}",
                entity_type="ap_payment",
                entity_id=payment_id,
                source_service="erp.ap",
            )
        except Exception:
            pass


payment_service = PaymentService()
