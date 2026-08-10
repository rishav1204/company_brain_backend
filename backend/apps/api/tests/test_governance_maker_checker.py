from app.modules.platform.governance.engine.rule_engine import evaluate_rule


def test_payment_threshold_rule_blocks_without_cfo() -> None:
    rule = {
        "policy_key": "payment_threshold_cfo",
        "policy_type": "approval",
        "conditions": {"amount_gt": 1000000},
        "actions": {"block": True, "require_role": "cfo"},
    }
    blocked = evaluate_rule(rule, {"amount": 2_000_000}, ["manager"])
    assert blocked is not None
    assert "cfo" in blocked.lower()
