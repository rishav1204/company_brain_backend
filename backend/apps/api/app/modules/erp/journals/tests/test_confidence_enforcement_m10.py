import pytest

from app.modules.erp.journals.ai.confidence_engine import requires_finance_review
from app.modules.erp.journals.services.journal_validation_service import journal_validation_service


def test_requires_finance_review_true() -> None:
    assert requires_finance_review({"requires_review": True}) is True


def test_requires_finance_review_cleared_after_review() -> None:
    assert requires_finance_review({"requires_review": True, "reviewed_at": True}) is False


def test_validate_approve_blocks_low_confidence() -> None:
    journal = {"ai_confidence": {"requires_review": True}}
    with pytest.raises(ValueError, match="finance review"):
        journal_validation_service.ensure_ai_reviewed(journal)
