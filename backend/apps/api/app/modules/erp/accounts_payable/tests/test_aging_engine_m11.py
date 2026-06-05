from app.modules.erp.accounts_payable.engine.aging_engine import aging_bucket, aging_days, bucket_invoice


def test_aging_days_overdue() -> None:
    assert aging_days(due_date="2026-05-01", as_of="2026-06-05") == 35


def test_bucket_31_60() -> None:
    assert aging_bucket(35) == "31-60"


def test_bucket_current() -> None:
    assert aging_bucket(-2) == "current"


def test_bucket_invoice() -> None:
    item = bucket_invoice(
        {"due_date": "2026-05-01", "total_amount": 1000, "paid_amount": 200},
        as_of="2026-06-05",
    )
    assert item["outstanding"] == 800
    assert item["bucket"] == "31-60"
