from app.modules.erp.tax.engine.itc_engine import evaluate_itc_eligibility


def test_itc_eligible() -> None:
    result = evaluate_itc_eligibility(itc_type="IGST", amount=1000, blocked_rules=[], itc_eligible_mapping=True)
    assert result["status"] == "eligible"
    assert result["eligible_amount"] == 1000


def test_itc_blocked() -> None:
    rules = [{"category": "motor_vehicle", "block_percentage": 100, "is_active": True}]
    result = evaluate_itc_eligibility(
        itc_type="IGST", amount=1000, blocked_rules=rules, itc_eligible_mapping=True, expense_category="motor_vehicle",
    )
    assert result["status"] == "blocked"


def test_itc_ineligible_mapping() -> None:
    result = evaluate_itc_eligibility(itc_type="CGST", amount=500, blocked_rules=[], itc_eligible_mapping=False)
    assert result["status"] == "ineligible"
