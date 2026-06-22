from __future__ import annotations

from app.modules.erp.accounts_receivable.engine.collection_engine import build_receipt_journal_lines
from app.modules.erp.vouchers.generators.base_generator import BaseVoucherGenerator


class ReceiptGenerator(BaseVoucherGenerator):
    def generate_lines(self, org_id: str, *, payload: dict) -> list[dict]:
        return build_receipt_journal_lines(
            bank_account_id=str(payload["bank_account_id"]),
            receivable_account_id=str(payload["receivable_account_id"]),
            amount=float(payload["amount"]),
        )


receipt_generator = ReceiptGenerator()
