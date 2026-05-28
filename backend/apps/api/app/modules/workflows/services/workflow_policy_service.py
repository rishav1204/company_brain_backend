from __future__ import annotations

from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker
from app.services.object_context import ObjectContext


def validate_approval_authority(
    *,
    org_id: str,
    user_id: str,
    roles: list[str],
    action: str,
    object_context: ObjectContext,
    attrs: dict | None,
    created_by: str | None,
    human_approved: bool = False,
) -> tuple[bool, str | None]:
    try:
        enforce_maker_checker(created_by=created_by, actor_user_id=user_id, org_id=org_id)
    except MakerCheckerViolation as exc:
        return False, str(exc)
    decision = evaluate_access(
        org_id=org_id,
        user_id=user_id,
        roles=roles,
        action=action,
        object_context=object_context,
        attrs=attrs,
        created_by=created_by,
        human_approved=human_approved,
    )
    if not decision.allowed:
        return False, decision.reason
    return True, None
