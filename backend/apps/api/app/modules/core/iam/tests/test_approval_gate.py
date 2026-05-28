from app.modules.core.iam.services.approval_gate_service import requires_human_approval


def test_critical_action_always_requires_approval() -> None:
    assert requires_human_approval(action="approve_payment", amount=100, attrs={})


def test_iam_role_cap_overrides_legacy_50k() -> None:
    assert not requires_human_approval(
        action="read",
        amount=100000,
        attrs={"max_approve_amount": 500000},
    )


def test_legacy_50k_when_no_iam_attrs() -> None:
    assert requires_human_approval(action="read", amount=60000, attrs={})
