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
from app.modules.erp.procurement.services.po_invoice_line_service import (
    build_invoice_lines_from_po,
    validate_po_invoice_prerequisites,
)
from app.modules.platform.events.events.erp_events import emit_invoice_approved, emit_invoice_created
from app.services.logger import log_event


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
        branch_id: str | None = None,
    ) -> dict:
        from app.core.config import settings
        from app.modules.erp.security.company_resolution_service import company_resolution_service

        vendor = vendor_repository.get(org_id, vendor_id=vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        if settings.erp_require_company_id:
            company_id = company_resolution_service.resolve_for_write(
                org_id, company_id=company_id, operation="ap.invoice.create"
            )
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

        fuzzy = duplicate_invoice_service.check_fuzzy_duplicate(
            org_id,
            vendor_id=vendor_id,
            invoice_number=invoice_number,
            total_amount=total_amount,
            invoice_date=invoice_date,
        )
        if fuzzy and fuzzy.get("duplicate"):
            raise ValueError(f"Probable duplicate invoice: {fuzzy.get('reason')}")

        if purchase_order_id:
            validate_po_invoice_prerequisites(
                org_id, purchase_order_id=purchase_order_id, goods_receipt_id=goods_receipt_id
            )

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
        if goods_receipt_id:
            invoice_meta["grn_id"] = goods_receipt_id

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
            branch_id=branch_id,
        )
        iid = str(invoice["id"])
        self._link_prediction_if_present(org_id, invoice_id=iid, metadata=invoice_meta)
        if lines:
            invoice_line_repository.replace_lines(org_id, invoice_id=iid, lines=lines)
        elif purchase_order_id:
            po_lines = build_invoice_lines_from_po(
                org_id,
                purchase_order_id=purchase_order_id,
                expense_account_id=expense_account_id,
                goods_receipt_id=goods_receipt_id,
            )
            invoice_line_repository.replace_lines(org_id, invoice_id=iid, lines=po_lines)
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
            from app.modules.erp.procurement.services.matching_service import matching_service

            matching_service.run_match(
                org_id,
                po_id=purchase_order_id,
                grn_id=goods_receipt_id,
                ap_invoice_id=iid,
            )

        return self.get_invoice(org_id, invoice_id=iid)

    def get_invoice(self, org_id: str, *, invoice_id: str) -> dict:
        invoice = invoice_repository.get(org_id, invoice_id=invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        # Use resolved UUID — invoice_id may be a document number (INV-001)
        resolved_id = str(invoice.get("id") or invoice_id)
        lines = invoice_line_repository.list_by_invoice(org_id, invoice_id=resolved_id)
        return {"invoice": invoice, "lines": lines}

    def list_invoices(
        self,
        org_id: str,
        *,
        status: str | None = None,
        vendor_id: str | None = None,
        branch_ids: list[str] | None = None,
    ) -> list[dict]:
        return invoice_repository.list(org_id, status=status, vendor_id=vendor_id, branch_ids=branch_ids)

    def _link_prediction_if_present(self, org_id: str, *, invoice_id: str, metadata: dict) -> None:
        prediction_id = str(metadata.get("prediction_id") or "").strip()
        if not prediction_id:
            return
        try:
            from app.modules.erp.ports.intelligence_registry import intelligence_registry

            intelligence_registry.invoice().link_prediction(org_id, prediction_id, ap_invoice_id=invoice_id)
        except Exception as exc:
            log_event("ap.invoice.prediction_link_failed", org_id=org_id, invoice_id=invoice_id, error=str(exc))

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
        except Exception as exc:
            log_event("ap.invoice.workflow_start_optional_failed", org_id=org_id, invoice_id=invoice_id, detail=str(exc))
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
            except Exception as exc:
                log_event("ap.invoice.grni_lookup_failed", org_id=org_id, detail=str(exc))
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

        # INT-08/INT-09: Optional invoice-level TDS deduction (enterprise config).
        # Only enabled when caller sets invoice metadata `tds_deduct_at_invoice=true`.
        if bool(meta.get("tds_deduct_at_invoice")):
            try:
                from app.modules.erp.tax.services.tds_posting_service import resolve_tds_payable_account
                from app.modules.erp.tax.services.tds_service import tds_service

                tds_payable_id = resolve_tds_payable_account(org_id)
                if not tds_payable_id:
                    raise ValueError("TDS payable account mapping required for invoice-level TDS")

                invoice_date = str(invoice.get("invoice_date") or "")[:10]
                gross = float(invoice.get("invoice_amount") or invoice.get("total_amount") or 0)
                tds_calc = tds_service.preview_for_invoice(
                    org_id,
                    vendor_id=str(invoice["vendor_id"]),
                    gross_amount=gross,
                    expense_category=str(meta.get("expense_category") or ""),
                    payment_type=str(meta.get("payment_type") or vendor_meta.get("vendor_type") or ""),
                )
                tds_amount = float(tds_calc.get("tds_amount") or 0)
                if tds_amount > 0:
                    # Reduce vendor payable credit by TDS and add TDS payable credit line.
                    adjusted = False
                    for line in journal_lines:
                        if str(line.get("account_id")) == str(payable_id) and float(line.get("credit_amount") or 0) > 0:
                            line["credit_amount"] = float(line.get("credit_amount") or 0) - tds_amount
                            if float(line["credit_amount"]) < 0:
                                raise ValueError("Invoice-level TDS exceeds vendor payable line")
                            adjusted = True
                            break
                    if not adjusted:
                        raise ValueError("Unable to locate vendor payable line for invoice-level TDS adjustment")
                    journal_lines.append(
                        {
                            "account_id": tds_payable_id,
                            "debit_amount": 0,
                            "credit_amount": tds_amount,
                            "line_description": "TDS payable (deducted at invoice)",
                        }
                    )
                    meta["tds_at_invoice"] = True
                    meta["tds_invoice_calc"] = tds_calc
            except Exception as exc:
                raise ValueError(f"Invoice-level TDS setup failed: {exc}") from exc
        from app.modules.erp.journals.services.journal_draft_conn import approve_with_conn, create_draft_with_conn
        from app.services.db import get_db_conn, set_rls_org

        post_result = None
        jid = None
        journal = None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            # If invoice-level TDS enabled and applicable, persist the TDS transaction row inside the same transaction.
            if bool(meta.get("tds_deduct_at_invoice")) and bool(meta.get("tds_at_invoice")):
                try:
                    from app.modules.erp.tax.services.tds_service import tds_service

                    invoice_date = str(invoice.get("invoice_date") or "")[:10]
                    gross = float(invoice.get("invoice_amount") or invoice.get("total_amount") or 0)
                    tds_service.deduct_for_ap_invoice_with_conn(
                        conn,
                        org_id,
                        invoice_id=invoice_id,
                        vendor_id=str(invoice["vendor_id"]),
                        invoice_date=invoice_date,
                        gross_amount=gross,
                        expense_category=str(meta.get("expense_category") or ""),
                        payment_type=str(meta.get("payment_type") or vendor_meta.get("vendor_type") or ""),
                    )
                except Exception as exc:
                    raise ValueError(f"Invoice-level TDS persistence failed: {exc}") from exc
            journal = create_draft_with_conn(
                conn,
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
            approve_with_conn(conn, org_id, journal_id=jid, approver_id=approver_id)
            invoice_repository.set_status_conn(
                conn,
                org_id,
                invoice_id=invoice_id,
                status="approved",
                approved_by=approver_id,
                journal_id=jid,
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
                invoice_repository.patch_metadata_conn(conn, org_id, invoice_id=invoice_id, metadata=meta)
            except Exception as exc:
                log_event("ap.invoice.tds_preview_failed", org_id=org_id, invoice_id=invoice_id, detail=str(exc))
            if auto_post:
                post_result = posting_orchestrator.post_journal_with_conn(
                    conn, org_id, journal_id=jid, posted_by=approver_id, defer_side_effects=True
                )
            conn.commit()

        # Side effects after commit only.
        if auto_post and journal:
            posting_orchestrator._emit_post_side_effects(
                org_id,
                journal_id=jid,
                journal=journal["journal"],
                batch_id=str((post_result or {}).get("ledger_batch_id") or ""),
                posted_by=approver_id,
            )
        emit_invoice_approved(org_id, invoice_id=invoice_id)
        vendor_balance_service.refresh_vendor(org_id, vendor_id=str(invoice["vendor_id"]))
        ap_realtime_service.push_invoice_approved(org_id, invoice_id=invoice_id, approver_id=approver_id)
        self._audit(org_id, invoice_id=invoice_id, action="ap.invoice.approved", actor_id=approver_id)

        try:
            from app.modules.erp.vouchers.services.voucher_projection_service import voucher_projection_service

            voucher_projection_service.project_operational(
                org_id,
                voucher_type="purchase",
                reference_type="ap_invoice",
                reference_id=invoice_id,
                source_module="accounts_payable",
                journal_id=jid,
                voucher_date=posting_date or str(invoice.get("invoice_date")),
                narration=f"AP Invoice {invoice.get('invoice_number')}",
                company_id=invoice.get("company_id"),
                created_by=approver_id,
                status="posted" if auto_post else "journal_generated",
                total_amount=float(invoice.get("total_amount") or 0),
            )
        except Exception as exc:
            log_event("ap.invoice.voucher_projection_failed", org_id=org_id, invoice_id=invoice_id, detail=str(exc))

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
        except Exception as exc:
            log_event("ap.invoice.audit_optional_failed", org_id=org_id, invoice_id=invoice_id, action=action, detail=str(exc))


invoice_service = InvoiceService()
