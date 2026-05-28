from app.modules.workflows.engine.condition_evaluator import evaluate_condition, step_should_run


def test_vendor_risk_condition() -> None:
    assert evaluate_condition({"vendor_risk": "HIGH"}, {"vendor_risk": "high"})
    assert not evaluate_condition({"vendor_risk": "HIGH"}, {"vendor_risk": "low"})


def test_step_conditions_gate() -> None:
    step = {"conditions": {"amount": {"op": "gte", "value": 1000}}}
    assert step_should_run(step, {"amount": 5000})
    assert not step_should_run(step, {"amount": 100})
