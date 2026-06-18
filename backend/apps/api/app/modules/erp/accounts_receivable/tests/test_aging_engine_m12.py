from app.modules.erp.accounts_receivable.engine.aging_engine import aging_bucket, bucket_invoice


def test_aging_buckets_extended() -> None:
    assert aging_bucket(0) == "current"
    assert aging_bucket(45) == "31-60"
    assert aging_bucket(200) == "180+"
    assert aging_bucket(400) == "365+"


def test_bucket_invoice() -> None:
    result = bucket_invoice({"due_date": "2020-01-01", "total_amount": 1000, "paid_amount": 0}, as_of="2026-06-01")
    assert result["outstanding"] == 1000
    assert result["bucket"] in {"180+", "365+"}
