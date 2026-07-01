from app.modules.core.iam.repositories.auth_audit_repository import auth_audit_repo


def record_auth_event(
    *,
    event: str,
    success: bool = True,
    org_id: str | None = None,
    user_id: str | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    session_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    try:
        auth_audit_repo.record(
            event=event,
            success=success,
            org_id=org_id,
            user_id=user_id,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            metadata=metadata,
        )
    except Exception:
        pass
