from app.modules.workflows.engine.branch_resolver import get_escalation_policies, resolve_execution_path


def test_branch_resolver_picks_matching_branch() -> None:
    definition = {
        "branches": [
            {"when": {"amount": {"op": "gte", "value": 100000}}, "steps": [{"key": "cfo", "type": "human_approval"}]},
            {"when": {"amount": {"op": "lte", "value": 99999}}, "steps": [{"key": "mgr", "type": "human_approval"}]},
        ]
    }
    high = resolve_execution_path(definition, {"amount": 150000})
    low = resolve_execution_path(definition, {"amount": 5000})
    assert high[0]["key"] == "cfo"
    assert low[0]["key"] == "mgr"


def test_escalation_policies_from_definition() -> None:
    definition = {"escalation_policies": [{"type": "finance_escalation", "when": {"amount": {"op": "gte", "value": 1}}}]}
    policies = get_escalation_policies(definition)
    assert policies[0]["type"] == "finance_escalation"
