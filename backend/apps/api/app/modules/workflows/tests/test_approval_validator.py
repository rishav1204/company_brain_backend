import pytest

from app.modules.workflows.validators.approval_validator import validate_decision


def test_validate_decision_normalizes() -> None:
    assert validate_decision("approve") == "approved"
    assert validate_decision("reject") == "rejected"


def test_validate_decision_invalid() -> None:
    with pytest.raises(ValueError):
        validate_decision("maybe")
