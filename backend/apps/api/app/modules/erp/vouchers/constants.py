from __future__ import annotations

VOUCHER_TYPES = frozenset({
    "sales",
    "purchase",
    "payment",
    "receipt",
    "contra",
    "journal",
    "debit_note",
    "credit_note",
})

VOUCHER_TYPE_TO_JOURNAL_TYPE = {
    "sales": "sales",
    "purchase": "purchase",
    "payment": "payment",
    "receipt": "receipt",
    "contra": "contra",
    "journal": "general",
    "debit_note": "adjustment",
    "credit_note": "adjustment",
}

VOUCHER_TYPE_PREFIX = {
    "sales": "SAL",
    "purchase": "PUR",
    "payment": "PAY",
    "receipt": "REC",
    "contra": "CNT",
    "journal": "JRN",
    "debit_note": "DBN",
    "credit_note": "CRN",
}

EDITABLE_STATUSES = frozenset({"draft", "validated"})
POSTABLE_STATUSES = frozenset({"approved", "journal_generated"})
