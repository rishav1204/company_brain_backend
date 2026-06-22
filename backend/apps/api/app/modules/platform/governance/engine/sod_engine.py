from __future__ import annotations

AGENT_DENIED_ACTIONS = frozenset(
    {
        "post_journal",
        "journal.post",
        "payment.execute",
        "approve_payment",
        "gst.file",
        "invoice.approve",
        "execute",
        "payment.approve",
    }
)


def check_sod(*, action: str, created_by: str | None, actor_user_id: str | None, org_id: str) -> str | None:
    from app.modules.core.iam.services.maker_checker_service import (
        MakerCheckerViolation,
        enforce_maker_checker,
        requires_maker_checker,
    )

    if not requires_maker_checker(action):
        return None
    try:
        enforce_maker_checker(created_by=created_by, actor_user_id=actor_user_id, org_id=org_id)
    except MakerCheckerViolation as exc:
        return str(exc)
    return None


def check_agent_restrictions(*, actor_type: str | None, action: str) -> str | None:
    if str(actor_type or "").lower() not in {"agent", "ai", "system"}:
        return None
    normalized = action.strip().lower()
    if normalized in AGENT_DENIED_ACTIONS or any(normalized.endswith(s) for s in (".post", ".execute", ".file", ".approve")):
        if normalized in AGENT_DENIED_ACTIONS or normalized.endswith((".post", ".execute", ".file")):
            return f"Agent cannot perform action: {action}"
    return None
