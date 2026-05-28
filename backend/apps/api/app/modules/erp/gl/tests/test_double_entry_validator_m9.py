from app.modules.erp.gl.validators.double_entry_validator import validate_double_entry


def test_double_entry_balanced() -> None:
    lines = [{"debit_amount": 100, "credit_amount": 0}, {"debit_amount": 0, "credit_amount": 100}]
    d, c = validate_double_entry(lines)
    assert d == 100
    assert c == 100


def test_double_entry_unbalanced() -> None:
    lines = [{"debit_amount": 100, "credit_amount": 0}, {"debit_amount": 0, "credit_amount": 99.99}]
    try:
        validate_double_entry(lines)
        assert False, "expected error"
    except ValueError as exc:
        assert "debits" in str(exc).lower()

