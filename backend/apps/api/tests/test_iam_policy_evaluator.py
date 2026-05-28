from unittest.mock import patch

from app.modules.core.iam.services.policy_evaluator import evaluate_iam_permission
from app.services.object_context import ObjectContext


@patch("app.modules.core.iam.services.policy_evaluator.has_permission", return_value=True)
def test_maker_checker_denied_on_self_approval(_mock_perm) -> None:
    decision = evaluate_iam_permission(
        org_id="org-1",
        user_id="user-1",
        roles=["tenant_admin"],
        permission_key="payment.approve",
        action="approve_payment",
        object_context=ObjectContext(object_type="invoice", object_id="inv-1", amount=100.0),
        attrs={"max_approve_amount": 1000000},
        actor_user_id="user-1",
        created_by="user-1",
        human_approved=True,
    )
    assert decision.allowed is False
    assert "maker_checker" in decision.reason.lower() or "Maker-checker" in decision.reason


@patch("app.modules.core.iam.services.policy_evaluator.has_permission", return_value=False)
def test_missing_permission_denied(_mock_perm) -> None:
    decision = evaluate_iam_permission(
        org_id="org-1",
        user_id="user-1",
        roles=["analyst"],
        permission_key="payment.approve",
        action="approve_payment",
        object_context=ObjectContext(object_type="invoice", object_id="inv-1", amount=100.0),
    )
    assert decision.allowed is False
    assert decision.reason == "missing_permission"
