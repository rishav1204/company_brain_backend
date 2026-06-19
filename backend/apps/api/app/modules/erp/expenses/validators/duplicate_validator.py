from __future__ import annotations

import hashlib


def receipt_hash(*, document_id: str | None, amount: float, merchant: str, expense_date: str, employee_id: str) -> str:
    raw = f"{document_id}|{amount}|{merchant}|{expense_date}|{employee_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
