from __future__ import annotations

from app.modules.erp.accounts_payable.engine.payment_engine import build_payment_journal_lines
from app.modules.erp.vouchers.generators.base_generator import BaseVoucherGenerator


class PaymentGenerator(BaseVoucherGenerator):
    def generate_lines(self, org_id: str, *, payload: dict) -> list[dict]:
        return build_payment_journal_lines(
            payable_account_id=str(payload["payable_account_id"]),
            bank_account_id=str(payload["bank_account_id"]),
            amount=float(payload["amount"]),
        )


payment_generator = PaymentGenerator()
