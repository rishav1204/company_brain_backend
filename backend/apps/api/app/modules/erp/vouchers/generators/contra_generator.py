from __future__ import annotations

from app.modules.erp.vouchers.generators.base_generator import BaseVoucherGenerator


class ContraGenerator(BaseVoucherGenerator):
    def generate_lines(self, org_id: str, *, payload: dict) -> list[dict]:
        amount = float(payload["amount"])
        return [
            {
                "account_id": str(payload["to_account_id"]),
                "debit_amount": amount,
                "credit_amount": 0,
                "line_description": payload.get("narration") or "Contra debit",
            },
            {
                "account_id": str(payload["from_account_id"]),
                "debit_amount": 0,
                "credit_amount": amount,
                "line_description": payload.get("narration") or "Contra credit",
            },
        ]


contra_generator = ContraGenerator()
