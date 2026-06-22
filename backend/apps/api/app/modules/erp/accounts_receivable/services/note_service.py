from __future__ import annotations

from app.modules.erp.accounts_receivable.engine.receivable_engine import (
    build_sales_journal_lines,
    resolve_receivable_account,
    resolve_revenue_account,
)
from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository
from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
from app.modules.erp.journals.services.approval_service import approval_service as journal_approval_service
from app.modules.erp.journals.services.journal_service import journal_service
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.modules.erp.vouchers.generators import lines_for_voucher
from app.modules.erp.vouchers.services.voucher_projection_service import voucher_projection_service
from app.modules.erp.vouchers.services.voucher_service import voucher_service
from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created


class ArNoteService:
    def _validate_reference(self, org_id: str, *, reference_invoice_id: str, note_amount: float) -> dict:
        ref = ar_invoice_repository.get(org_id, invoice_id=reference_invoice_id)
        if not ref:
            raise ValueError("Reference invoice not found")
        if str(ref.get("document_type") or "invoice") != "invoice":
            raise ValueError("Reference must be a standard invoice")
        if str(ref.get("status")) not in {"issued", "partially_paid", "paid", "overdue"}:
            raise ValueError("Reference invoice must be issued before creating a note")
        outstanding = float(ref.get("total_amount") or 0) - float(ref.get("paid_amount") or 0)
        if note_amount > outstanding + 0.01:
            raise ValueError("Note amount exceeds reference invoice outstanding balance")
        return ref

    def create_credit_note(
        self,
        org_id: str,
        *,
        reference_invoice_id: str,
        invoice_number: str,
        invoice_date: str,
        due_date: str,
        amount: float,
        gst_amount: float,
        total_amount: float,
        created_by: str | None = None,
        narration: str | None = None,
    ) -> dict:
        ref = self._validate_reference(org_id, reference_invoice_id=reference_invoice_id, note_amount=total_amount)
        note = ar_invoice_repository.create_note(
            org_id,
            customer_id=str(ref["customer_id"]),
            document_type="credit_note",
            reference_invoice_id=reference_invoice_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=due_date,
            subtotal=amount,
            gst_amount=gst_amount,
            total_amount=total_amount,
            company_id=ref.get("company_id"),
            created_by=created_by,
            metadata={"narration": narration},
        )
        customer = customer_repository.get(org_id, customer_id=str(ref["customer_id"])) or {}
        receivable_id = resolve_receivable_account(org_id, customer)
        revenue_id = resolve_revenue_account(org_id, customer)
        payload = {
            "receivable_account_id": receivable_id,
            "revenue_account_id": revenue_id,
            "amount": amount,
            "subtotal": amount,
            "gst_amount": gst_amount,
            "total_amount": total_amount,
            "company_id": ref.get("company_id"),
        }
        voucher = voucher_service.create(
            org_id,
            voucher_type="credit_note",
            voucher_date=invoice_date,
            lines=lines_for_voucher(org_id, voucher_type="credit_note", payload=payload),
            narration=narration or f"AR credit note {invoice_number}",
            company_id=ref.get("company_id"),
            reference_type="ar_credit_note",
            reference_id=str(note["id"]),
            created_by=created_by,
            source_module="accounts_receivable",
            generator_payload=payload,
        )
        ar_invoice_repository.link_voucher(org_id, invoice_id=str(note["id"]), voucher_id=str(voucher["voucher"]["id"]))
        return {"note": note, "voucher": voucher}

    def create_debit_note(
        self,
        org_id: str,
        *,
        reference_invoice_id: str,
        invoice_number: str,
        invoice_date: str,
        due_date: str,
        amount: float,
        gst_amount: float,
        total_amount: float,
        created_by: str | None = None,
        narration: str | None = None,
    ) -> dict:
        ref = self._validate_reference(org_id, reference_invoice_id=reference_invoice_id, note_amount=total_amount)
        note = ar_invoice_repository.create_note(
            org_id,
            customer_id=str(ref["customer_id"]),
            document_type="debit_note",
            reference_invoice_id=reference_invoice_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=due_date,
            subtotal=amount,
            gst_amount=gst_amount,
            total_amount=total_amount,
            company_id=ref.get("company_id"),
            created_by=created_by,
            metadata={"narration": narration},
        )
        customer = customer_repository.get(org_id, customer_id=str(ref["customer_id"])) or {}
        receivable_id = resolve_receivable_account(org_id, customer)
        revenue_id = resolve_revenue_account(org_id, customer)
        payload = {
            "receivable_account_id": receivable_id,
            "revenue_account_id": revenue_id,
            "amount": amount,
            "subtotal": amount,
            "gst_amount": gst_amount,
            "total_amount": total_amount,
            "company_id": ref.get("company_id"),
        }
        voucher = voucher_service.create(
            org_id,
            voucher_type="sales",
            voucher_date=invoice_date,
            lines=lines_for_voucher(org_id, voucher_type="sales", payload=payload),
            narration=narration or f"AR debit note {invoice_number}",
            company_id=ref.get("company_id"),
            reference_type="ar_debit_note",
            reference_id=str(note["id"]),
            created_by=created_by,
            source_module="accounts_receivable",
            generator_payload=payload,
        )
        ar_invoice_repository.link_voucher(org_id, invoice_id=str(note["id"]), voucher_id=str(voucher["voucher"]["id"]))
        return {"note": note, "voucher": voucher}

    def submit_for_approval(self, org_id: str, *, note_id: str, submitted_by: str) -> dict:
        note = ar_invoice_repository.get(org_id, invoice_id=note_id)
        if not note:
            raise ValueError("Note not found")
        handle_entity_created(
            org_id=org_id,
            payload={
                "entity_type": "ar_credit_note",
                "entity_id": note_id,
                "amount": float(note.get("total_amount") or 0),
                "started_by": submitted_by,
                "metadata": {"note_id": note_id, "ar_invoice_id": note_id},
            },
        )
        return {"note_id": note_id, "status": "pending_approval"}

    def approve_note(
        self,
        org_id: str,
        *,
        note_id: str,
        approver_id: str,
        auto_post: bool = True,
    ) -> dict:
        note = ar_invoice_repository.get(org_id, invoice_id=note_id)
        if not note:
            raise ValueError("Note not found")
        doc_type = str(note.get("document_type") or "")
        if doc_type not in {"credit_note", "debit_note"}:
            raise ValueError("Document is not an AR note")

        customer = customer_repository.get(org_id, customer_id=str(note["customer_id"])) or {}
        receivable_id = resolve_receivable_account(org_id, customer)
        revenue_id = resolve_revenue_account(org_id, customer)
        if doc_type == "credit_note":
            journal_lines = build_sales_journal_lines(
                org_id,
                receivable_account_id=receivable_id,
                revenue_account_id=revenue_id,
                subtotal=float(note.get("subtotal") or 0),
                gst_amount=float(note.get("gst_amount") or 0),
                total_amount=float(note.get("total_amount") or 0),
                company_id=note.get("company_id"),
            )
            journal_lines = [
                {**line, "debit_amount": line.get("credit_amount") or 0, "credit_amount": line.get("debit_amount") or 0}
                for line in journal_lines
            ]
            voucher_type = "credit_note"
            reference_type = "ar_credit_note"
        else:
            journal_lines = build_sales_journal_lines(
                org_id,
                receivable_account_id=receivable_id,
                revenue_account_id=revenue_id,
                subtotal=float(note.get("subtotal") or 0),
                gst_amount=float(note.get("gst_amount") or 0),
                total_amount=float(note.get("total_amount") or 0),
                company_id=note.get("company_id"),
            )
            voucher_type = "sales"
            reference_type = "ar_debit_note"

        journal = journal_service.create_draft(
            org_id,
            created_by=None,
            journal_type="adjustment" if doc_type == "credit_note" else "sales",
            posting_date=str(note.get("invoice_date")),
            description=f"AR {doc_type} {note.get('invoice_number')}",
            source_type=reference_type,
            source_id=note_id,
            company_id=note.get("company_id"),
            lines=journal_lines,
            idempotency_key=f"ar-{doc_type}:{note_id}",
        )
        jid = str(journal["journal"]["id"])
        journal_approval_service.approve(org_id, journal_id=jid, approver_id=approver_id, skip_maker_checker=True)
        ar_invoice_repository.set_status(org_id, invoice_id=note_id, status="issued", issued_by=approver_id, journal_id=jid)
        post_result = None
        if auto_post:
            post_result = posting_orchestrator.post_journal(org_id, journal_id=jid, posted_by=approver_id)
        voucher_projection_service.project_operational(
            org_id,
            voucher_type=voucher_type,
            reference_type=reference_type,
            reference_id=note_id,
            source_module="accounts_receivable",
            journal_id=jid,
            voucher_date=str(note.get("invoice_date")),
            narration=f"AR {doc_type} {note.get('invoice_number')}",
            company_id=note.get("company_id"),
            created_by=approver_id,
            status="posted" if auto_post else "journal_generated",
            total_amount=float(note.get("total_amount") or 0),
        )
        return {"note_id": note_id, "status": "issued", "journal_id": jid, "post_result": post_result}


ar_note_service = ArNoteService()
