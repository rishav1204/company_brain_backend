def _reverse_lines(original: list[dict]) -> list[dict]:
    return [
        {
            "debit_amount": float(line.get("credit_amount") or 0),
            "credit_amount": float(line.get("debit_amount") or 0),
        }
        for line in original
    ]


def test_reversal_swaps_sides() -> None:
    original = [
        {"debit_amount": 1000, "credit_amount": 0},
        {"debit_amount": 0, "credit_amount": 1000},
    ]
    reversed_lines = _reverse_lines(original)
    assert reversed_lines[0]["debit_amount"] == 0
    assert reversed_lines[0]["credit_amount"] == 1000
    assert reversed_lines[1]["debit_amount"] == 1000
    assert reversed_lines[1]["credit_amount"] == 0


def test_reversal_preserves_balance() -> None:
    original = [
        {"debit_amount": 500, "credit_amount": 0},
        {"debit_amount": 200, "credit_amount": 0},
        {"debit_amount": 0, "credit_amount": 700},
    ]
    reversed_lines = _reverse_lines(original)
    d = sum(l["debit_amount"] for l in reversed_lines)
    c = sum(l["credit_amount"] for l in reversed_lines)
    assert round(d - c, 2) == 0
