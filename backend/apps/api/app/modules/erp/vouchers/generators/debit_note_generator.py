from __future__ import annotations

from app.modules.erp.tax.services.gst_posting_service import build_purchase_journal_lines
from app.modules.erp.vouchers.generators.base_generator import BaseVoucherGenerator


class DebitNoteGenerator(BaseVoucherGenerator):
    def generate_lines(self, org_id: str, *, payload: dict) -> list[dict]:
        return build_purchase_journal_lines(
            org_id,
            expense_account_id=str(payload["expense_account_id"]),
            payable_account_id=str(payload["payable_account_id"]),
            invoice_amount=float(payload.get("amount") or payload.get("invoice_amount") or 0),
            gst_amount=float(payload.get("gst_amount") or 0),
            total_amount=float(payload["total_amount"]),
            gst_lines=payload.get("gst_lines"),
            company_id=payload.get("company_id"),
        )


debit_note_generator = DebitNoteGenerator()
