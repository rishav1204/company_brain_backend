from pathlib import Path

from app.modules.erp.vouchers.constants import VOUCHER_TYPE_PREFIX, VOUCHER_TYPE_TO_JOURNAL_TYPE, VOUCHER_TYPES
from app.modules.erp.vouchers.generators import journal_type_for_voucher, resolve_generator


def test_voucher_types_complete() -> None:
    assert len(VOUCHER_TYPES) == 8
    for vtype in VOUCHER_TYPES:
        assert vtype in VOUCHER_TYPE_TO_JOURNAL_TYPE
        assert vtype in VOUCHER_TYPE_PREFIX
        resolve_generator(vtype)


def test_journal_type_mapping() -> None:
    assert journal_type_for_voucher("journal") == "general"
    assert journal_type_for_voucher("debit_note") == "adjustment"
    assert journal_type_for_voucher("contra") == "contra"


def test_payment_generator_balanced() -> None:
    gen = resolve_generator("payment")
    lines = gen.generate_lines(
        "org-test",
        payload={
            "payable_account_id": "a1",
            "bank_account_id": "a2",
            "amount": 1000.0,
        },
    )
    debits = sum(float(l.get("debit_amount") or 0) for l in lines)
    credits = sum(float(l.get("credit_amount") or 0) for l in lines)
    assert debits == credits == 1000.0


def test_contra_generator_balanced() -> None:
    gen = resolve_generator("contra")
    lines = gen.generate_lines(
        "org-test",
        payload={"from_account_id": "b1", "to_account_id": "b2", "amount": 500.0},
    )
    debits = sum(float(l.get("debit_amount") or 0) for l in lines)
    credits = sum(float(l.get("credit_amount") or 0) for l in lines)
    assert debits == credits == 500.0
