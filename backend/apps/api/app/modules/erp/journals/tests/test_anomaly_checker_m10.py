from app.modules.erp.journals.ai.anomaly_checker import detect_journal_anomalies


def test_detect_zero_total() -> None:
    anomalies = detect_journal_anomalies([])
    assert any(a["code"] == "zero_total" for a in anomalies)
