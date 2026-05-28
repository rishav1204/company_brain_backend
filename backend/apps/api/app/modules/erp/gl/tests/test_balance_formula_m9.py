def _closing(nature: str, debit: float, credit: float) -> float:
    nature = (nature or "debit").lower()
    return (debit - credit) if nature == "debit" else (credit - debit)


def test_balance_formula_debit_nature() -> None:
    assert _closing("debit", 120, 20) == 100


def test_balance_formula_credit_nature() -> None:
    assert _closing("credit", 120, 20) == -100
    assert _closing("credit", 20, 120) == 100

