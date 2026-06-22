from __future__ import annotations

from app.modules.erp.accounts_receivable.engine.receivable_engine import build_sales_journal_lines
from app.modules.erp.vouchers.generators.base_generator import BaseVoucherGenerator


class SalesGenerator(BaseVoucherGenerator):
    def generate_lines(self, org_id: str, *, payload: dict) -> list[dict]:
        return build_sales_journal_lines(
            org_id,
            receivable_account_id=str(payload["receivable_account_id"]),
            revenue_account_id=str(payload["revenue_account_id"]),
            subtotal=float(payload.get("subtotal") or payload.get("invoice_amount") or 0),
            gst_amount=float(payload.get("gst_amount") or 0),
            total_amount=float(payload["total_amount"]),
            gst_lines=payload.get("gst_lines"),
            company_id=payload.get("company_id"),
        )


sales_generator = SalesGenerator()
