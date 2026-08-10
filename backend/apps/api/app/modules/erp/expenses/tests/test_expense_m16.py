from app.modules.finance_os.domain_intelligence.expenses.expense_classifier import classify_expense, fraud_score
from app.modules.finance_os.domain_intelligence.expenses.fraud_detector import detect as detect_fraud
from app.modules.erp.expenses.validators.claim_validator import (
    ensure_approvable,
    ensure_cancellable,
    ensure_submittable,
)
from app.modules.erp.expenses.validators.duplicate_validator import receipt_hash
from app.modules.erp.expenses.validators.policy_validator import validate_policy_amount, validate_receipt_required
from app.modules.erp.expenses.workflows.claim_approval_workflow import resolve_approval_chain, workflow_metadata
from app.modules.platform.documents.ai.receipt_extractor import extract as receipt_extract
from app.services.event_consumers import _handle_expense_workflow_approval


def test_classify_meal() -> None:
    assert classify_expense({"merchant": "Cafe Coffee Day", "raw_text": "restaurant bill"}) == "meal"


def test_classify_hotel() -> None:
    assert classify_expense({"merchant": "Taj Hotel", "raw_text": "lodging"}) == "hotel"


def test_classify_travel() -> None:
    assert classify_expense({"merchant": "Uber Trip", "raw_text": "cab fare"}) == "travel"


def test_fraud_score_low_confidence() -> None:
    score = fraud_score({"confidence_score": 0.4}, amount=1000)
    assert score >= 30


def test_fraud_detector() -> None:
    result = detect_fraud({"confidence_score": 0.3}, amount=9999)
    assert result["requires_review"] is True


def test_receipt_hash_stable() -> None:
    h1 = receipt_hash(document_id="doc1", amount=100, merchant="Cafe", expense_date="2026-01-01", employee_id="u1")
    h2 = receipt_hash(document_id="doc1", amount=100, merchant="Cafe", expense_date="2026-01-01", employee_id="u1")
    assert h1 == h2


def test_receipt_extractor() -> None:
    data = receipt_extract("Cafe Delight\nTotal: 450.00\n2026-06-18")
    assert data.get("amount") == 450.0
    assert "merchant" in data


def test_claim_submittable_validator() -> None:
    try:
        ensure_submittable("approved")
        assert False
    except ValueError:
        assert True


def test_claim_approvable_validator() -> None:
    ensure_approvable("submitted")
    try:
        ensure_approvable("draft")
        assert False
    except ValueError:
        assert True


def test_claim_cancellable_validator() -> None:
    ensure_cancellable("draft")
    try:
        ensure_cancellable("paid")
        assert False
    except ValueError:
        assert True


def test_policy_amount_limit() -> None:
    msg = validate_policy_amount(amount=1500, max_amount=1000)
    assert msg is not None


def test_policy_receipt_required() -> None:
    msg = validate_receipt_required(amount=600, receipt_mandatory_above=500, has_receipt=False)
    assert msg is not None


def test_approval_chain_under_5k() -> None:
    chain = resolve_approval_chain(4000)
    assert chain == ["manager"]


def test_approval_chain_over_50k() -> None:
    chain = resolve_approval_chain(75000)
    assert chain[-1] == "controller"


def test_workflow_metadata() -> None:
    meta = workflow_metadata(12000, claim_id="claim-1")
    assert meta["claim_id"] == "claim-1"
    assert meta["amount"] == 12000


def test_spend_category_totals() -> None:
    claims = [
        {"total_amount": 100, "expense_category": "meal"},
        {"total_amount": 200, "expense_category": "travel"},
    ]
    by_type: dict[str, float] = {}
    total = 0.0
    for c in claims:
        amt = float(c.get("total_amount") or 0)
        cat = str(c.get("expense_category") or "uncategorized")
        by_type[cat] = by_type.get(cat, 0) + amt
        total += amt
    assert total == 300
    assert by_type["meal"] == 100


def test_expense_workflow_unknown() -> None:
    assert _handle_expense_workflow_approval("org", {"entity_type": "other"}) is False
