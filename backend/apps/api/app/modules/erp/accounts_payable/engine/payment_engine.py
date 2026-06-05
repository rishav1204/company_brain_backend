from __future__ import annotations


def build_payment_journal_lines(*, payable_account_id: str, bank_account_id: str, amount: float) -> list[dict]:
    """Payment: Payable Dr + Bank Cr"""
    return [
        {
            "account_id": payable_account_id,
            "debit_amount": amount,
            "credit_amount": 0,
            "line_description": "Vendor payable settlement",
        },
        {
            "account_id": bank_account_id,
            "debit_amount": 0,
            "credit_amount": amount,
            "line_description": "Bank payment",
        },
    ]


def compute_discount(*, invoice_amount: float, discount_rate: float) -> float:
    return round(float(invoice_amount) * float(discount_rate), 2)
