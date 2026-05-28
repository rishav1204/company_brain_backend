from app.modules.platform.governance.services.audit_service import audit_service
from app.modules.platform.governance.services.policy_service import governance_policy_service


def test_audit_record_and_policy_dry_run() -> None:
    result = governance_policy_service.evaluate(
        "org-int",
        action="invoice.approve",
        attrs={},
        roles=["approver"],
        created_by="u1",
        actor_user_id="u2",
        dry_run=True,
    )
    assert result.allowed is True
    h = audit_service.hash_prompt("integration test")
    assert len(h) == 64
