from app.modules.core.iam.services.branch_scope_service import evaluate_branch_scope
from app.services.policy_service import PolicyDecision


def test_branch_scope_denied() -> None:
    decision = evaluate_branch_scope(
        attrs={"allowed_branch_ids": ["branch-a"]},
        object_branch_id="branch-b",
        object_company_id=None,
    )
    assert decision is not None
    assert decision.allowed is False


def test_branch_scope_allowed() -> None:
    decision = evaluate_branch_scope(
        attrs={"allowed_branch_ids": ["branch-a"]},
        object_branch_id="branch-a",
        object_company_id=None,
    )
    assert decision is None
