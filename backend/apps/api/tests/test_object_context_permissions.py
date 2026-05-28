from app.services.object_context import ObjectContext
from app.services import policy_service


def test_high_amount_invoice_requires_elevated_role() -> None:
    decision = policy_service.evaluate_object_permission(
        roles=["analyst"],
        action="approve_payment",
        object_context=ObjectContext(
            object_type="invoice",
            object_id="inv-1",
            amount=75000.0,
            vendor_risk="medium",
            status="Pending",
        ),
    )
    assert decision.allowed is False
    assert decision.reason == "amount_exceeds_role_threshold"
    assert "amount_threshold_denied" in (decision.checks or [])


def test_high_vendor_risk_requires_controller_role() -> None:
    decision = policy_service.evaluate_object_permission(
        roles=["analyst"],
        action="approve_payment",
        object_context=ObjectContext(
            object_type="invoice",
            object_id="inv-2",
            amount=1200.0,
            vendor_risk="high",
            status="Pending",
        ),
    )
    assert decision.allowed is False
    assert decision.reason == "high_vendor_risk_requires_elevated_role"


def test_terminal_invoice_state_denies_approval() -> None:
    decision = policy_service.evaluate_object_permission(
        roles=["tenant_admin"],
        action="approve_payment",
        object_context=ObjectContext(
            object_type="invoice",
            object_id="inv-3",
            amount=100.0,
            status="Paid",
        ),
        human_approved=True,
    )
    assert decision.allowed is False
    assert decision.reason == "object_not_actionable_in_current_state"


def test_owner_preparer_sod_on_workflow_object() -> None:
    decision = policy_service.evaluate_object_permission(
        roles=["ap_preparer"],
        action="post_journal",
        object_context=ObjectContext(
            object_type="workflow",
            object_id="wf-1",
            owner_user_id="user-1",
            status="pending_approval",
        ),
        actor_user_id="user-1",
    )
    assert decision.allowed is False
    assert "owner_sod_denied" in (decision.checks or [])


def test_department_scope_denied_when_attrs_mismatch() -> None:
    decision = policy_service.evaluate_object_permission(
        roles=["tenant_admin"],
        action="notify_user",
        object_context=ObjectContext(
            object_type="workflow",
            object_id="wf-2",
            workflow_type="treasury",
        ),
        attrs={"allowed_departments": ["ap", "ar"]},
        human_approved=True,
    )
    assert decision.allowed is False
    assert decision.reason == "department_scope_denied"
