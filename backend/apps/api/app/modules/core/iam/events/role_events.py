from app.services.event_bus import event_bus


def emit_role_assigned(
    *,
    org_id: str,
    user_id: str,
    role_name: str,
    trace_id: str,
    company_id: str | None = None,
    branch_id: str | None = None,
) -> None:
    event_bus.publish(
        event_type="role.assigned",
        org_id=org_id,
        source="iam",
        trace_id=trace_id,
        payload={
            "user_id": user_id,
            "role_name": role_name,
            "company_id": company_id,
            "branch_id": branch_id,
        },
    )


def emit_permission_denied(*, org_id: str, user_id: str, action: str, reason: str) -> None:
    event_bus.publish(
        event_type="permission.denied",
        org_id=org_id,
        source="iam",
        trace_id=f"deny-{user_id}-{action}",
        payload={"user_id": user_id, "action": action, "reason": reason},
    )


def emit_session_revoked(*, org_id: str, user_id: str, session_id: str, trace_id: str) -> None:
    event_bus.publish(
        event_type="session.revoked",
        org_id=org_id,
        source="iam",
        trace_id=trace_id,
        payload={"user_id": user_id, "session_id": session_id},
    )
