from __future__ import annotations

from app.modules.erp.accounts_receivable.engine.receivable_engine import build_sales_journal_lines
from app.modules.erp.vouchers.generators.base_generator import BaseVoucherGenerator


class CreditNoteGenerator(BaseVoucherGenerator):
    def generate_lines(self, org_id: str, *, payload: dict) -> list[dict]:
        lines = build_sales_journal_lines(
            org_id,
            receivable_account_id=str(payload["receivable_account_id"]),
            revenue_account_id=str(payload["revenue_account_id"]),
            subtotal=float(payload.get("amount") or payload.get("subtotal") or 0),
            gst_amount=float(payload.get("gst_amount") or 0),
            total_amount=float(payload["total_amount"]),
            gst_lines=payload.get("gst_lines"),
            company_id=payload.get("company_id"),
        )
        return [
            {
                **line,
                "debit_amount": line.get("credit_amount") or 0,
                "credit_amount": line.get("debit_amount") or 0,
                "line_description": (line.get("line_description") or "Credit note reversal"),
            }
            for line in lines
        ]


credit_note_generator = CreditNoteGenerator()
