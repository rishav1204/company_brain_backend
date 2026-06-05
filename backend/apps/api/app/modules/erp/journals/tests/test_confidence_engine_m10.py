from app.modules.erp.journals.ai.confidence_engine import score_journal_confidence


def test_confidence_high_no_review() -> None:
    result = score_journal_confidence(ledger_confidence=0.96, gst_confidence=0.99, vendor_confidence=0.97)
    assert result["requires_review"] is False
    assert result["overall"] >= 0.85


def test_confidence_low_requires_review() -> None:
    result = score_journal_confidence(ledger_confidence=0.5, gst_confidence=0.99, vendor_confidence=0.97)
    assert result["requires_review"] is True
