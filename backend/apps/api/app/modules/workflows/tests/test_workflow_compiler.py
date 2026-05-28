from app.modules.workflows.engine.workflow_compiler import compile_definition, resolve_threshold_role


def test_compile_definition_steps() -> None:
    plan = compile_definition(
        {
            "steps": [
                {"key": "review", "type": "ai_review", "optional": True},
                {"key": "approve", "type": "human_approval", "sla_hours": 24},
            ]
        }
    )
    assert len(plan) == 2
    assert plan[0]["key"] == "review"
    assert plan[1]["sla_hours"] == 24


def test_threshold_routing() -> None:
    definition = {
        "thresholds": [
            {"max_amount": 100000, "role": "ap_executive"},
            {"max_amount": 1000000, "role": "finance_manager"},
            {"max_amount": None, "role": "cfo"},
        ]
    }
    assert resolve_threshold_role(definition, 50000) == "ap_executive"
    assert resolve_threshold_role(definition, 500000) == "finance_manager"
    assert resolve_threshold_role(definition, 5000000) == "cfo"
