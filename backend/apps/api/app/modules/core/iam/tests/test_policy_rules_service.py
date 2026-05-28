from app.modules.core.iam.services.policy_rules_service import evaluate_policy_context_rules
from app.services.policy_service import PolicyDecision


def test_amount_lt_rule_denies_at_threshold() -> None:
    ctx = {"rules": [{"resource": "payment", "action": "approve", "condition": {"amount_lt": 500000}}]}
    decision = evaluate_policy_context_rules(
        policy_context=ctx,
        resource="payment",
        action="approve",
        amount=500000,
    )
    assert decision is not None
    assert decision.allowed is False


def test_fiscal_period_closed_rule() -> None:
    ctx = {"rules": [{"resource": "journal", "action": "post", "condition": {"fiscal_period_open": True}}]}
    decision = evaluate_policy_context_rules(
        policy_context=ctx,
        resource="journal",
        action="post",
        fiscal_period_open=False,
    )
    assert decision is not None
    assert decision.reason == "fiscal_period_closed"


def test_branch_amount_outside_limit() -> None:
    ctx = {
        "rules": [
            {
                "resource": "payment",
                "action": "approve",
                "condition": {"branch_amount_outside_limit": 1000000},
            }
        ]
    }
    decision = evaluate_policy_context_rules(
        policy_context=ctx,
        resource="payment",
        action="approve",
        amount=1500000,
        branch_id="branch-b",
        allowed_branch_ids=["branch-a"],
    )
    assert decision is not None
    assert "branch" in decision.reason
