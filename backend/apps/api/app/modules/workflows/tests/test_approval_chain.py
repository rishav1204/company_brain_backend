from app.modules.workflows.engine.approval_chain import build_approval_chain, inject_conditional_approvers


def test_multi_level_threshold_chain() -> None:
    definition = {
        "thresholds": [
            {"max_amount": 100000, "role": "ap_executive"},
            {"max_amount": 1000000, "role": "finance_manager"},
            {"max_amount": None, "role": "cfo"},
        ]
    }
    chain = build_approval_chain(definition, {"amount": 500000})
    roles = [r["role"] for r in chain]
    assert roles == ["ap_executive", "finance_manager"]


def test_conditional_legal_approver() -> None:
    definition = {"conditional_approvals": [{"when": {"vendor_risk": "HIGH"}, "role": "legal"}]}
    chain = inject_conditional_approvers([{"level": 1, "role": "ap_executive"}], definition, {"vendor_risk": "HIGH"})
    assert chain[0]["role"] == "legal"
