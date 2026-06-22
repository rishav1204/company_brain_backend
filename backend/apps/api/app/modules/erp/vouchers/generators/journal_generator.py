from __future__ import annotations

from app.modules.erp.vouchers.generators.base_generator import BaseVoucherGenerator


class JournalGenerator(BaseVoucherGenerator):
    def generate_lines(self, org_id: str, *, payload: dict) -> list[dict]:
        lines = payload.get("lines") or []
        return [
            {
                "account_id": str(line["account_id"]),
                "debit_amount": float(line.get("debit_amount") or 0),
                "credit_amount": float(line.get("credit_amount") or 0),
                "line_description": line.get("narration") or line.get("line_description"),
                "cost_center_id": line.get("cost_center_id"),
                "tax_code": line.get("tax_code"),
            }
            for line in lines
        ]


journal_generator = JournalGenerator()
