import pytest

from app.modules.erp.journals.services.accrual_service import compute_accrual_amount


def test_accrual_formula_estimated_minus_paid() -> None:
    assert compute_accrual_amount(estimated_expense=1000, paid_amount=200) == 800


def test_accrual_formula_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        compute_accrual_amount(estimated_expense=100, paid_amount=100)
