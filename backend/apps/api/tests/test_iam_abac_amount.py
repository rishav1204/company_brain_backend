from app.modules.core.iam.services.abac_service import evaluate_amount_limit


def test_abac_amount_limit_denied() -> None:
    decision = evaluate_amount_limit({"max_approve_amount": 500000}, 600000.0)
    assert decision is not None
    assert decision.allowed is False
    assert decision.reason == "amount_exceeds_role_abac_limit"


def test_abac_amount_within_limit() -> None:
    decision = evaluate_amount_limit({"max_approve_amount": 500000}, 400000.0)
    assert decision is None
