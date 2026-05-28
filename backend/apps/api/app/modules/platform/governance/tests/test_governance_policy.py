from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation
from app.modules.platform.governance.services.policy_service import governance_policy_service


def test_maker_checker_blocks_same_actor() -> None:
    result = governance_policy_service.evaluate(
        "org-test",
        action="invoice.approve",
        attrs={},
        roles=["approver"],
        created_by="user-1",
        actor_user_id="user-1",
        dry_run=True,
    )
    assert result.allowed is False
    assert any(v.get("type") == "maker_checker" for v in result.violations)


def test_maker_checker_allows_different_actor() -> None:
    result = governance_policy_service.evaluate(
        "org-test",
        action="invoice.approve",
        attrs={},
        roles=["approver"],
        created_by="user-1",
        actor_user_id="user-2",
        dry_run=True,
    )
    assert result.allowed is True


def test_enforce_maker_checker_raises() -> None:
    from app.modules.core.iam.services.maker_checker_service import enforce_maker_checker

    try:
        enforce_maker_checker(created_by="a", actor_user_id="a")
        raised = False
    except MakerCheckerViolation:
        raised = True
    assert raised
