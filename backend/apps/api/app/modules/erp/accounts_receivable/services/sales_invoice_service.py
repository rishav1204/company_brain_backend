from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.accounts_receivable.engine.account_resolver import (
    build_output_gst_lines,
    resolve_receivable_account,
    resolve_revenue_account,
)
from app.modules.erp.accounts_receivable.engine.receivable_engine import build_sales_journal_lines, build_writeoff_journal_lines
from app.modules.erp.accounts_receivable.events.ar_events import emit_invoice_issued, emit_sales_invoice_created
from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository
from app.modules.erp.accounts_receivable.repositories.invoice_line_repository import ar_invoice_line_repository
from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
from app.modules.erp.accounts_receivable.services.ar_realtime_service import ar_realtime_service
from app.modules.erp.accounts_receivable.services.credit_limit_service import credit_limit_service
from app.modules.erp.accounts_receivable.services.customer_balance_service import customer_balance_service
from app.modules.erp.accounts_receivable.services.revenue_recognition_service import revenue_recognition_service
from app.modules.erp.accounts_receivable.validators.invoice_validator import invoice_validator
from app.modules.erp.journals.services.approval_service import approval_service as journal_approval_service
from app.modules.erp.journals.services.journal_service import journal_service
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator


class SalesInvoiceService:
    def create_invoice(
        self,
        org_id: str,
        *,
        customer_id: str,
        invoice_number: str,
        invoice_date: str,
        subtotal: float,
        gst_amount: float,
        total_amount: float,
        due_date: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        lines: list[dict] | None = None,
        metadata: dict | None = None,
        contract_months: int | None = None,
        cgst: float = 0,
        sgst: float = 0,
        igst: float = 0,
        gst_rate: float | None = None,
        export_zero_rated: bool = False,
    ) -> dict:
        customer = customer_repository.get(org_id, customer_id=customer_id)
        if not customer:
            raise ValueError("Customer not found")
        invoice_validator.validate_amounts(subtotal=subtotal, gst_amount=gst_amount, total_amount=total_amount)
        self._validate_gst_amounts(
            subtotal=subtotal,
            gst_amount=gst_amount,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            gst_rate=gst_rate,
            export_zero_rated=export_zero_rated or str(customer.get("customer_type")) == "export",
        )
        if not due_date:
            terms = int(customer.get("payment_terms_days") or 30)
            due_date = (date.fromisoformat(invoice_date[:10]) + timedelta(days=terms)).isoformat()

        revenue_recognition = {}
        if contract_months and contract_months > 1:
            revenue_recognition = revenue_recognition_service.build_schedule(
                contract_value=subtotal,
                contract_months=contract_months,
                start_date=invoice_date,
            )

        invoice = ar_invoice_repository.create(
            org_id,
            customer_id=customer_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=due_date,
            subtotal=subtotal,
            gst_amount=gst_amount,
            total_amount=total_amount,
            company_id=company_id,
            created_by=created_by,
            metadata=metadata or {},
            revenue_recognition=revenue_recognition,
        )
        iid = str(invoice["id"])
        if lines:
            ar_invoice_line_repository.replace_lines(org_id, invoice_id=iid, lines=lines)
        else:
            revenue_id = resolve_revenue_account(org_id, customer)
            gst_line_defs = build_output_gst_lines(
                org_id, cgst=cgst, sgst=sgst, igst=igst, gst_amount=gst_amount,
                company_id=company_id, export_zero_rated=export_zero_rated or str(customer.get("customer_type")) == "export",
            )
            default_lines = []
            if revenue_id and subtotal > 0:
                default_lines.append({"account_id": revenue_id, "line_type": "revenue", "amount": subtotal, "description": "Revenue"})
            for gl in gst_line_defs:
                default_lines.append({
                    "account_id": gl["account_id"], "line_type": "gst", "amount": gl["amount"],
                    "tax_code": gl.get("tax_code"), "description": "Output GST",
                })
            if default_lines:
                ar_invoice_line_repository.replace_lines(org_id, invoice_id=iid, lines=default_lines)

        emit_sales_invoice_created(org_id, invoice_id=iid, amount=total_amount, customer_id=customer_id)
        self._audit(org_id, invoice_id=iid, action="ar.invoice.created", actor_id=created_by)
        return self.get_invoice(org_id, invoice_id=iid)

    def get_invoice(self, org_id: str, *, invoice_id: str) -> dict:
        invoice = ar_invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        lines = ar_invoice_line_repository.list_by_invoice(org_id, invoice_id=invoice_id)
        return {"invoice": invoice, "lines": lines}

    def list_invoices(self, org_id: str, *, status: str | None = None, customer_id: str | None = None) -> list[dict]:
        return ar_invoice_repository.list(org_id, status=status, customer_id=customer_id)

    def issue_invoice(
        self,
        org_id: str,
        *,
        invoice_id: str,
        issued_by: str,
        auto_post: bool = True,
        force_credit_approval: bool = False,
    ) -> dict:
        invoice = ar_invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        invoice_validator.ensure_issuable(str(invoice.get("status")))

        from app.modules.erp.fiscal.services.posting_guard import ensure_posting_allowed

        posting_date = str(invoice.get("invoice_date") or "")[:10]
        if posting_date:
            ensure_posting_allowed(org_id, posting_date)

        credit = credit_limit_service.check_before_issue(
            org_id, customer_id=str(invoice["customer_id"]), invoice_amount=float(invoice.get("total_amount") or 0)
        )
        if credit.get("block"):
            raise ValueError("Credit limit exceeded — invoice blocked")
        if credit.get("requires_approval") and not force_credit_approval:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "sales_invoice",
                    "entity_id": invoice_id,
                    "workflow_key": "AR_INVOICE_APPROVAL",
                    "amount": float(invoice.get("total_amount") or 0),
                    "started_by": issued_by,
                    "metadata": {"ar_invoice_id": invoice_id, "customer_id": invoice.get("customer_id"), "credit_check": credit},
                },
            )
            return {"invoice_id": invoice_id, "status": "draft", "pending_credit_approval": True, "credit_check": credit}

        customer = customer_repository.get(org_id, customer_id=str(invoice["customer_id"])) or {}
        receivable_id = resolve_receivable_account(org_id, customer)
        revenue_id = resolve_revenue_account(org_id, customer)
        if not receivable_id or not revenue_id:
            raise ValueError("Receivable and revenue accounts required")

        subtotal = float(invoice.get("subtotal") or 0)
        invoice_date = str(invoice.get("invoice_date") or "")[:10]
        inv_meta = invoice.get("metadata") if isinstance(invoice.get("metadata"), dict) else {}
        apply_tcs = bool(inv_meta.get("apply_tcs") or inv_meta.get("tcs_applicable"))
        tcs_result = None
        if apply_tcs:
            from app.modules.erp.tax.services.tax_account_setup_service import tax_account_setup_service
            from app.modules.erp.tax.services.tcs_service import tcs_service

            tax_account_setup_service.ensure_tax_accounts(org_id, company_id=invoice.get("company_id"))
            tcs_result = tcs_service.collect_for_invoice(
                org_id,
                invoice_id=invoice_id,
                customer_id=str(invoice["customer_id"]),
                gross_amount=subtotal,
                invoice_date=invoice_date,
                pan_present=bool(customer.get("pan") or customer.get("gstin")),
            )

        lines_data = ar_invoice_line_repository.list_by_invoice(org_id, invoice_id=invoice_id)
        gst_lines = [
            {"account_id": l.get("account_id"), "amount": l["amount"], "tax_code": l.get("tax_code"), "description": l.get("description")}
            for l in lines_data if str(l.get("line_type")) == "gst"
        ]

        if tcs_result and tcs_result.get("applicable"):
            from app.modules.erp.tax.services.tds_posting_service import build_sale_journal_lines_with_tcs, resolve_tcs_payable_account

            journal_lines = build_sale_journal_lines_with_tcs(
                receivable_account_id=receivable_id,
                revenue_account_id=revenue_id,
                tcs_payable_account_id=resolve_tcs_payable_account(org_id),
                gross_amount=subtotal,
                tcs_amount=float(tcs_result.get("tcs_amount") or 0),
                total_collected=float(tcs_result.get("total_collected") or subtotal),
            )
            if gst_lines:
                for gl in gst_lines:
                    journal_lines.append({
                        "account_id": gl["account_id"],
                        "debit_amount": 0,
                        "credit_amount": gl["amount"],
                        "line_description": gl.get("description") or "Output GST",
                        "tax_code": gl.get("tax_code"),
                    })
                journal_lines[0]["debit_amount"] = round(
                    float(journal_lines[0]["debit_amount"]) + float(invoice.get("gst_amount") or 0), 2
                )
        else:
            journal_lines = build_sales_journal_lines(
                org_id,
                receivable_account_id=receivable_id,
                revenue_account_id=revenue_id,
                subtotal=subtotal,
                gst_amount=float(invoice.get("gst_amount") or 0),
                total_amount=float(invoice.get("total_amount") or 0),
                gst_lines=gst_lines or None,
                company_id=invoice.get("company_id"),
            )
        journal = journal_service.create_draft(
            org_id,
            created_by=None,
            journal_type="sales",
            posting_date=str(invoice.get("invoice_date")),
            description=f"AR Invoice {invoice.get('invoice_number')}",
            source_type="ar_invoice",
            source_id=invoice_id,
            company_id=invoice.get("company_id"),
            lines=journal_lines,
            idempotency_key=f"ar-invoice:{invoice_id}",
        )
        jid = str(journal["journal"]["id"])
        journal_approval_service.approve(org_id, journal_id=jid, approver_id=issued_by, skip_maker_checker=True)

        ar_invoice_repository.set_status(org_id, invoice_id=invoice_id, status="issued", issued_by=issued_by, journal_id=jid)
        customer_balance_service.refresh_customer(org_id, customer_id=str(invoice["customer_id"]))
        emit_invoice_issued(org_id, invoice_id=invoice_id, amount=float(invoice.get("total_amount") or 0), customer_id=str(invoice["customer_id"]))
        ar_realtime_service.push_invoice_issued(org_id, invoice_id=invoice_id, amount=float(invoice.get("total_amount") or 0))
        self._audit(org_id, invoice_id=invoice_id, action="ar.invoice.issued", actor_id=issued_by)

        post_result = None
        if auto_post:
            post_result = posting_orchestrator.post_journal(org_id, journal_id=jid, posted_by=issued_by)

        try:
            from app.modules.erp.vouchers.services.voucher_projection_service import voucher_projection_service

            voucher_projection_service.project_operational(
                org_id,
                voucher_type="sales",
                reference_type="ar_invoice",
                reference_id=invoice_id,
                source_module="accounts_receivable",
                journal_id=jid,
                voucher_date=posting_date or str(invoice.get("invoice_date")),
                narration=f"AR Invoice {invoice.get('invoice_number')}",
                company_id=invoice.get("company_id"),
                created_by=issued_by,
                status="posted" if auto_post else "journal_generated",
                total_amount=float(invoice.get("total_amount") or 0),
            )
        except Exception:
            pass

        return {"invoice_id": invoice_id, "status": "issued", "journal_id": jid, "post_result": post_result, "credit_check": credit}

    def cancel_invoice(self, org_id: str, *, invoice_id: str, actor_id: str | None) -> dict:
        invoice = ar_invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        invoice_validator.ensure_cancellable(str(invoice.get("status")))
        if str(invoice.get("status")) in {"partially_paid", "paid"}:
            raise ValueError("Cannot cancel paid invoice")

        from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker

        try:
            enforce_maker_checker(created_by=str(invoice.get("created_by") or ""), actor_user_id=actor_id or "", org_id=org_id)
        except MakerCheckerViolation as exc:
            raise ValueError(str(exc)) from exc

        ar_invoice_repository.set_status(org_id, invoice_id=invoice_id, status="cancelled")
        self._audit(org_id, invoice_id=invoice_id, action="ar.invoice.cancelled", actor_id=actor_id)
        return {"invoice_id": invoice_id, "status": "cancelled"}

    def write_off_invoice(
        self,
        org_id: str,
        *,
        invoice_id: str,
        approver_id: str,
        bad_debt_account_id: str,
        auto_post: bool = True,
    ) -> dict:
        """Request write-off approval workflow; execution happens after workflow.approved."""
        return self.request_write_off(
            org_id,
            invoice_id=invoice_id,
            requested_by=approver_id,
            bad_debt_account_id=bad_debt_account_id,
            auto_post=auto_post,
        )

    def request_write_off(
        self,
        org_id: str,
        *,
        invoice_id: str,
        requested_by: str,
        bad_debt_account_id: str,
        auto_post: bool = True,
    ) -> dict:
        invoice = ar_invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        if str(invoice.get("status")) not in {"issued", "partially_paid", "overdue"}:
            raise ValueError("Invoice not eligible for write-off")

        from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker

        try:
            enforce_maker_checker(
                created_by=str(invoice.get("created_by") or ""),
                actor_user_id=requested_by,
                org_id=org_id,
            )
        except MakerCheckerViolation as exc:
            raise ValueError(str(exc)) from exc

        meta = invoice.get("metadata") if isinstance(invoice.get("metadata"), dict) else {}
        meta.update({
            "writeoff_pending": True,
            "bad_debt_account_id": bad_debt_account_id,
            "writeoff_auto_post": auto_post,
            "writeoff_requested_by": requested_by,
            "writeoff_workflow_approved": False,
        })
        ar_invoice_repository.update_metadata(org_id, invoice_id=invoice_id, metadata=meta)

        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "ar_writeoff",
                    "entity_id": invoice_id,
                    "workflow_key": "AR_WRITE_OFF_APPROVAL",
                    "amount": float(invoice.get("total_amount") or 0),
                    "started_by": requested_by,
                    "metadata": {
                        "ar_invoice_id": invoice_id,
                        "bad_debt_account_id": bad_debt_account_id,
                        "auto_post": auto_post,
                    },
                },
            )
        except Exception as exc:
            raise ValueError(f"Write-off workflow initiation failed: {exc}") from exc

        self._audit(org_id, invoice_id=invoice_id, action="ar.invoice.writeoff.requested", actor_id=requested_by)
        return {
            "invoice_id": invoice_id,
            "status": str(invoice.get("status")),
            "writeoff_approval_pending": True,
            "bad_debt_account_id": bad_debt_account_id,
        }

    def execute_write_off(
        self,
        org_id: str,
        *,
        invoice_id: str,
        approver_id: str,
        bad_debt_account_id: str | None = None,
        auto_post: bool | None = None,
        skip_workflow_check: bool = False,
    ) -> dict:
        invoice = ar_invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        if str(invoice.get("status")) in {"written_off", "paid", "cancelled"}:
            raise ValueError("Invoice not eligible for write-off")
        if str(invoice.get("status")) not in {"issued", "partially_paid", "overdue"}:
            raise ValueError("Invoice not eligible for write-off")

        meta = invoice.get("metadata") if isinstance(invoice.get("metadata"), dict) else {}
        if not skip_workflow_check and not meta.get("writeoff_workflow_approved"):
            if not meta.get("writeoff_pending"):
                raise ValueError("Write-off workflow approval required")
            raise ValueError("Write-off workflow not yet approved")

        debt_account = bad_debt_account_id or meta.get("bad_debt_account_id")
        if not debt_account:
            raise ValueError("Bad debt account required")
        post_flag = auto_post if auto_post is not None else bool(meta.get("writeoff_auto_post", True))

        customer = customer_repository.get(org_id, customer_id=str(invoice["customer_id"])) or {}
        receivable_id = resolve_receivable_account(org_id, customer)
        if not receivable_id:
            raise ValueError("Receivable account required")
        amount = max(0.0, float(invoice.get("total_amount") or 0) - float(invoice.get("paid_amount") or 0))
        journal_lines = build_writeoff_journal_lines(
            receivable_account_id=receivable_id,
            bad_debt_account_id=str(debt_account),
            amount=amount,
        )
        journal = journal_service.create_draft(
            org_id,
            created_by=None,
            journal_type="adjustment",
            posting_date=date.today().isoformat(),
            description=f"Write-off {invoice.get('invoice_number')}",
            source_type="ar_writeoff",
            source_id=invoice_id,
            company_id=invoice.get("company_id"),
            lines=journal_lines,
            idempotency_key=f"ar-writeoff:{invoice_id}",
        )
        jid = str(journal["journal"]["id"])
        journal_approval_service.approve(org_id, journal_id=jid, approver_id=approver_id, skip_maker_checker=True)
        ar_invoice_repository.set_status(org_id, invoice_id=invoice_id, status="written_off", journal_id=jid)
        meta.pop("writeoff_pending", None)
        meta["writeoff_workflow_approved"] = True
        meta["writeoff_executed_by"] = approver_id
        ar_invoice_repository.update_metadata(org_id, invoice_id=invoice_id, metadata=meta)
        customer_balance_service.refresh_customer(org_id, customer_id=str(invoice["customer_id"]))
        self._audit(org_id, invoice_id=invoice_id, action="ar.invoice.written_off", actor_id=approver_id)
        post_result = None
        if post_flag:
            post_result = posting_orchestrator.post_journal(org_id, journal_id=jid, posted_by=approver_id)
        return {"invoice_id": invoice_id, "status": "written_off", "journal_id": jid, "post_result": post_result}

    def _validate_gst_amounts(
        self,
        *,
        subtotal: float,
        gst_amount: float,
        cgst: float,
        sgst: float,
        igst: float,
        gst_rate: float | None,
        export_zero_rated: bool,
    ) -> None:
        if export_zero_rated:
            if gst_amount > 0:
                raise ValueError("Export/zero-rated invoices must have zero GST")
            return
        component_sum = round(float(cgst) + float(sgst) + float(igst), 2)
        if component_sum > 0 and abs(component_sum - gst_amount) > 0.05:
            raise ValueError(f"CGST+SGST+IGST ({component_sum}) must equal gst_amount ({gst_amount})")
        if gst_rate is not None and gst_amount > 0 and subtotal > 0:
            invoice_validator.validate_gst_calculation(
                taxable_value=subtotal, gst_rate=float(gst_rate), gst_amount=gst_amount
            )

    def _audit(self, org_id: str, *, invoice_id: str, action: str, actor_id: str | None) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=actor_id or "erp.ar",
                action=action,
                object_ref=f"erp:ar_invoice:{invoice_id}",
                entity_type="ar_invoice",
                entity_id=invoice_id,
                source_service="erp.ar",
            )
        except Exception:
            pass


sales_invoice_service = SalesInvoiceService()
