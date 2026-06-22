from __future__ import annotations

from app.modules.erp.vouchers.constants import VOUCHER_TYPE_TO_JOURNAL_TYPE
from app.modules.erp.vouchers.generators.contra_generator import contra_generator
from app.modules.erp.vouchers.generators.credit_note_generator import credit_note_generator
from app.modules.erp.vouchers.generators.debit_note_generator import debit_note_generator
from app.modules.erp.vouchers.generators.journal_generator import journal_generator
from app.modules.erp.vouchers.generators.payment_generator import payment_generator
from app.modules.erp.vouchers.generators.purchase_generator import purchase_generator
from app.modules.erp.vouchers.generators.receipt_generator import receipt_generator
from app.modules.erp.vouchers.generators.sales_generator import sales_generator

_GENERATORS = {
    "sales": sales_generator,
    "purchase": purchase_generator,
    "payment": payment_generator,
    "receipt": receipt_generator,
    "contra": contra_generator,
    "journal": journal_generator,
    "debit_note": debit_note_generator,
    "credit_note": credit_note_generator,
}


def resolve_generator(voucher_type: str):
    gen = _GENERATORS.get(voucher_type)
    if not gen:
        raise ValueError(f"No generator for voucher_type={voucher_type}")
    return gen


def lines_for_voucher(org_id: str, *, voucher_type: str, payload: dict) -> list[dict]:
    gen = resolve_generator(voucher_type)
    gen.validate_business_rules(org_id, payload=payload)
    return gen.generate_lines(org_id, payload=payload)


def journal_type_for_voucher(voucher_type: str) -> str:
    jt = VOUCHER_TYPE_TO_JOURNAL_TYPE.get(voucher_type)
    if not jt:
        raise ValueError(f"Unknown voucher_type={voucher_type}")
    return jt
