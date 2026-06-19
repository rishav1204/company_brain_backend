from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.accounts_payable.engine.account_resolver import resolve_expense_account
from app.modules.erp.accounts_payable.engine.payable_engine import resolve_default_payable_account
from app.modules.erp.accounts_payable.repositories.invoice_line_repository import invoice_line_repository
from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository
from app.modules.erp.accounts_payable.services.ap_realtime_service import ap_realtime_service
from app.modules.erp.accounts_payable.services.duplicate_invoice_service import duplicate_invoice_service
from app.modules.erp.accounts_payable.services.vendor_balance_service import vendor_balance_service
from app.modules.erp.accounts_payable.validators.invoice_validator import invoice_validator
from app.modules.erp.journals.services.approval_service import approval_service as journal_approval_service
from app.modules.erp.journals.services.journal_service import journal_service
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.modules.platform.events.events.erp_events import emit_invoice_approved, emit_invoice_created


class InvoiceService:
    def create_invoice(
        self,
        org_id: str,
        *,
        vendor_id: str,
        invoice_number: str,
        invoice_date: str,
        invoice_amount: float,
        gst_amount: float,
        total_amount: float,
        due_date: str | None = None,
        source_document_id: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        lines: list[dict] | None = None,
        expense_account_id: str | None = None,
        metadata: dict | None = None,
        purchase_order_id: str | None = None,
        goods_receipt_id: str | None = None,
    ) -> dict:
        vendor = vendor_repository.get(org_id, vendor_id=vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        invoice_validator.validate_amounts(
            invoice_amount=invoice_amount, gst_amount=gst_amount, total_amount=total_amount
        )
        dup = duplicate_invoice_service.check_duplicate(
            org_id,
            vendor_id=vendor_id,
            invoice_number=invoice_number,
            total_amount=total_amount,
            invoice_date=invoice_date,
        )
        if dup and dup.get("duplicate"):
            raise ValueError(f"Duplicate invoice detected: {dup['existing_invoice']['id']}")

        if not due_date:
            terms = int(vendor.get("payment_terms_days") or 30)
            due_date = (date.fromisoformat(invoice_date[:10]) + timedelta(days=terms)).isoformat()

        vendor_meta = vendor.get("metadata") if isinstance(vendor.get("metadata"), dict) else {}
        invoice_meta = {
            **(metadata or {}),
            "expense_account_id": expense_account_id,
            "early_payment_discount_rate": float(vendor_meta.get("early_payment_discount_rate") or 0),
            "early_payment_discount_days": int(vendor_meta.get("early_payment_discount_days") or 0),
        }

        invoice = invoice_repository.create(
            org_id,
            vendor_id=vendor_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=due_date,
            invoice_amount=invoice_amount,
            gst_amount=gst_amount,
            total_amount=total_amount,
            source_document_id=source_document_id,
            duplicate_checksum=dup.get("checksum") if dup else None,
            company_id=company_id,
            created_by=created_by,
            metadata=invoice_meta,
            purchase_order_id=purchase_order_id,
            goods_receipt_id=goods_receipt_id,
        )
        iid = str(invoice["id"])
        if lines:
            invoice_line_repository.replace_lines(org_id, invoice_id=iid, lines=lines)
        elif expense_account_id:
            invoice_line_repository.replace_lines(
                org_id,
                invoice_id=iid,
                lines=[
                    {"account_id": expense_account_id, "line_type": "expense", "amount": invoice_amount, "description": "Expense"},
                    {"line_type": "gst", "amount": gst_amount, "description": "GST", "tax_code": "IGST_INPUT"},
                ],
            )

        emit_invoice_created(org_id, invoice_id=iid, amount=total_amount, metadata={"vendor_id": vendor_id})
        self._audit(org_id, invoice_id=iid, action="ap.invoice.created", actor_id=created_by)
        if purchase_order_id:
            try:
                from app.modules.erp.procurement.services.matching_service import matching_service

                matching_service.run_match(
                    org_id,
                    po_id=purchase_order_id,
                    grn_id=goods_receipt_id,
                    ap_invoice_id=iid,
                )
            except Exception:
                pass
        return self.get_invoice(org_id, invoice_id=iid)

    def get_invoice(self, org_id: str, *, invoice_id: str) -> dict:
        invoice = invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        lines = invoice_line_repository.list_by_invoice(org_id, invoice_id=invoice_id)
        return {"invoice": invoice, "lines": lines}

    def list_invoices(self, org_id: str, *, status: str | None = None, vendor_id: str | None = None) -> list[dict]:
        return invoice_repository.list(org_id, status=status, vendor_id=vendor_id)

    def submit_for_review(self, org_id: str, *, invoice_id: str, actor_id: str | None) -> dict:
        invoice = invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        invoice_validator.ensure_editable(str(invoice.get("status")))
        invoice_repository.set_status(org_id, invoice_id=invoice_id, status="pending_review")
        return {"invoice_id": invoice_id, "status": "pending_review"}

    def confirm_review(self, org_id: str, *, invoice_id: str, actor_id: str | None) -> dict:
        invoice = invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        if str(invoice.get("status")) != "pending_review":
            raise ValueError("Invoice must be in pending_review to confirm")
        return self.submit_for_approval(org_id, invoice_id=invoice_id, actor_id=actor_id)

    def update_invoice(
        self,
        org_id: str,
        *,
        invoice_id: str,
        invoice_number: str | None = None,
        invoice_date: str | None = None,
        due_date: str | None = None,
        invoice_amount: float | None = None,
        gst_amount: float | None = None,
        total_amount: float | None = None,
        expense_account_id: str | None = None,
        lines: list[dict] | None = None,
        actor_id: str | None = None,
    ) -> dict:
        invoice = invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        invoice_validator.ensure_editable(str(invoice.get("status")))
        if invoice_amount is not None or gst_amount is not None or total_amount is not None:
            invoice_validator.validate_amounts(
                invoice_amount=float(invoice_amount if invoice_amount is not None else invoice.get("invoice_amount") or 0),
                gst_amount=float(gst_amount if gst_amount is not None else invoice.get("gst_amount") or 0),
                total_amount=float(total_amount if total_amount is not None else invoice.get("total_amount") or 0),
            )
        meta = invoice.get("metadata") if isinstance(invoice.get("metadata"), dict) else {}
        if expense_account_id:
            meta["expense_account_id"] = expense_account_id
        invoice_repository.update(
            org_id,
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=due_date,
            invoice_amount=invoice_amount,
            gst_amount=gst_amount,
            total_amount=total_amount,
            metadata=meta,
        )
        if lines is not None:
            invoice_line_repository.replace_lines(org_id, invoice_id=invoice_id, lines=lines)
        self._audit(org_id, invoice_id=invoice_id, action="ap.invoice.updated", actor_id=actor_id)
        return self.get_invoice(org_id, invoice_id=invoice_id)

    def submit_for_approval(self, org_id: str, *, invoice_id: str, actor_id: str | None) -> dict:
        invoice = invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        status = str(invoice.get("status"))
        if status not in {"draft", "pending_review"}:
            raise ValueError(f"Cannot submit invoice in status '{status}'")
        invoice_repository.set_status(org_id, invoice_id=invoice_id, status="pending_approval")
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "invoice",
                    "entity_id": invoice_id,
                    "amount": float(invoice.get("total_amount") or 0),
                    "started_by": actor_id,
                    "metadata": {"ap_invoice_id": invoice_id, "vendor_id": invoice.get("vendor_id")},
                },
            )
        except Exception:
            pass
        return {"invoice_id": invoice_id, "status": "pending_approval"}

    def approve(
        self,
        org_id: str,
        *,
        invoice_id: str,
        approver_id: str,
        expense_account_id: str | None = None,
        auto_post: bool = False,
    ) -> dict:
        invoice = invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        invoice_validator.ensure_approvable(str(invoice.get("status")))

        from app.modules.erp.fiscal.services.posting_guard import ensure_posting_allowed

        posting_date = str(invoice.get("invoice_date") or "")[:10]
        if posting_date:
            ensure_posting_allowed(org_id, posting_date)

        from app.modules.erp.procurement.services.matching_service import matching_service

        matching_service.ensure_invoice_approvable(
            org_id,
            ap_invoice_id=invoice_id,
            purchase_order_id=invoice.get("purchase_order_id"),
        )

        from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker

        try:
            enforce_maker_checker(
                created_by=str(invoice.get("created_by") or ""),
                actor_user_id=approver_id,
                org_id=org_id,
            )
        except MakerCheckerViolation as exc:
            raise ValueError(str(exc)) from exc

        vendor = vendor_repository.get(org_id, vendor_id=str(invoice["vendor_id"])) or {}
        meta = invoice.get("metadata") if isinstance(invoice.get("metadata"), dict) else {}
        vendor_meta = vendor.get("metadata") if isinstance(vendor.get("metadata"), dict) else {}
        expense_id = expense_account_id or meta.get("expense_account_id")
        if not expense_id:
            expense_id = resolve_expense_account(org_id)
        payable_id = resolve_default_payable_account(org_id, vendor)
        if not expense_id or not payable_id:
            raise ValueError("Expense and payable accounts required for journal creation")

        lines_data = invoice_line_repository.list_by_invoice(org_id, invoice_id=invoice_id)
        fixed_asset_lines = [l for l in lines_data if str(l.get("line_type")) == "fixed_asset" and l.get("account_id")]
        if fixed_asset_lines:
            expense_id = str(fixed_asset_lines[0]["account_id"])
        gst_lines = [
            {
                "account_id": l.get("account_id"),
                "amount": l["amount"],
                "tax_code": l.get("tax_code"),
                "description": l.get("description"),
            }
            for l in lines_data
            if str(l.get("line_type")) == "gst"
        ]
        grn_id = invoice.get("goods_receipt_id")
        use_grni = False
        is_rcm = bool(meta.get("reverse_charge") or meta.get("is_rcm"))
        if grn_id:
            try:
                from app.modules.erp.inventory.repositories.movement_repository import grn_link_repository

                grn_links = grn_link_repository.list_by_grn(org_id, goods_receipt_id=str(grn_id))
                use_grni = bool(grn_links)
            except Exception:
                use_grni = False

        if is_rcm:
            from app.modules.erp.tax.services.gst_posting_service import build_rcm_journal_lines

            journal_lines = build_rcm_journal_lines(
                org_id,
                expense_account_id=str(expense_id),
                payable_account_id=str(payable_id),
                invoice_amount=float(invoice.get("invoice_amount") or 0),
                gst_amount=float(invoice.get("gst_amount") or 0),
                gst_lines=gst_lines or None,
                company_id=invoice.get("company_id"),
            )
        elif use_grni:
            from app.modules.erp.inventory.engine.cogs_engine import build_grni_clearing_lines

            journal_lines = build_grni_clearing_lines(
                org_id,
                invoice_amount=float(invoice.get("invoice_amount") or 0),
                payable_account_id=str(payable_id),
                gst_lines=gst_lines or None,
            )
        else:
            from app.modules.erp.tax.services.gst_posting_service import build_purchase_journal_lines

            journal_lines = build_purchase_journal_lines(
                org_id,
                expense_account_id=str(expense_id),
                payable_account_id=str(payable_id),
                invoice_amount=float(invoice.get("invoice_amount") or 0),
                gst_amount=float(invoice.get("gst_amount") or 0),
                total_amount=float(invoice.get("total_amount") or 0),
                gst_lines=gst_lines or None,
                company_id=invoice.get("company_id"),
            )
        journal = journal_service.create_draft(
            org_id,
            created_by=None,
            journal_type="purchase",
            posting_date=str(invoice.get("invoice_date")),
            description=f"AP Invoice {invoice.get('invoice_number')}",
            source_type="ap_invoice",
            source_id=invoice_id,
            company_id=invoice.get("company_id"),
            lines=journal_lines,
            idempotency_key=f"ap-invoice:{invoice_id}",
        )
        jid = str(journal["journal"]["id"])
        journal_approval_service.approve(
            org_id, journal_id=jid, approver_id=approver_id, skip_maker_checker=True
        )

        invoice_repository.set_status(
            org_id, invoice_id=invoice_id, status="approved", approved_by=approver_id, journal_id=jid
        )
        try:
            from app.modules.erp.tax.services.tds_service import tds_service

            tds_preview = tds_service.preview_for_invoice(
                org_id,
                vendor_id=str(invoice["vendor_id"]),
                gross_amount=float(invoice.get("invoice_amount") or invoice.get("total_amount") or 0),
                expense_category=str(meta.get("expense_category") or ""),
                payment_type=str(meta.get("payment_type") or vendor_meta.get("vendor_type") or ""),
            )
            meta["tds_preview"] = tds_preview
            invoice_repository.patch_metadata(org_id, invoice_id=invoice_id, metadata=meta)
        except Exception:
            pass
        emit_invoice_approved(org_id, invoice_id=invoice_id)
        vendor_balance_service.refresh_vendor(org_id, vendor_id=str(invoice["vendor_id"]))
        ap_realtime_service.push_invoice_approved(org_id, invoice_id=invoice_id, approver_id=approver_id)
        self._audit(org_id, invoice_id=invoice_id, action="ap.invoice.approved", actor_id=approver_id)

        post_result = None
        if auto_post:
            post_result = posting_orchestrator.post_journal(org_id, journal_id=jid, posted_by=approver_id)

        return {
            "invoice_id": invoice_id,
            "status": "approved",
            "journal_id": jid,
            "post_result": post_result,
        }

    def cancel(self, org_id: str, *, invoice_id: str) -> dict:
        invoice = invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        if str(invoice.get("status")) in {"paid", "partially_paid"}:
            raise ValueError("Cannot cancel paid invoice")
        invoice_repository.set_status(org_id, invoice_id=invoice_id, status="cancelled")
        return {"invoice_id": invoice_id, "status": "cancelled"}

    def _audit(self, org_id: str, *, invoice_id: str, action: str, actor_id: str | None) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=actor_id or "erp.ap",
                action=action,
                object_ref=f"erp:ap_invoice:{invoice_id}",
                entity_type="ap_invoice",
                entity_id=invoice_id,
                source_service="erp.ap",
            )
        except Exception:
            pass


invoice_service = InvoiceService()
