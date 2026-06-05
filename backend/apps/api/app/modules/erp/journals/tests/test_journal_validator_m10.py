from app.modules.erp.journals.validators.journal_validator import journal_validator


def test_journal_validator_balance() -> None:
    lines = [{"account_id": "a1", "debit_amount": 100, "credit_amount": 0}, {"account_id": "a2", "debit_amount": 0, "credit_amount": 100}]
    d, c = journal_validator.validate_lines(lines)
    assert d == 100
    assert c == 100


def test_journal_validator_rejects_both_sides() -> None:
    lines = [
        {"account_id": "a1", "debit_amount": 50, "credit_amount": 50},
        {"account_id": "a2", "debit_amount": 0, "credit_amount": 50},
    ]
    try:
        journal_validator.validate_lines(lines)
        assert False, "expected error"
    except ValueError as exc:
        assert "both" in str(exc).lower()


def test_journal_status_guards() -> None:
    journal_validator.ensure_editable("draft")
    journal_validator.ensure_postable("approved")
    try:
        journal_validator.ensure_postable("draft")
        assert False, "expected error"
    except ValueError:
        assert True
