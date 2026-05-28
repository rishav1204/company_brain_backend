from app.services.event_bus import event_bus


def emit_user_created(*, org_id: str, user_id: str, email: str, trace_id: str) -> None:
    event_bus.publish(
        event_type="user.created",
        org_id=org_id,
        source="iam",
        trace_id=trace_id,
        payload={"user_id": user_id, "email": email},
    )


def emit_user_invited(*, org_id: str, invite_id: str, email: str, trace_id: str) -> None:
    event_bus.publish(
        event_type="user.invited",
        org_id=org_id,
        source="iam",
        trace_id=trace_id,
        payload={"invite_id": invite_id, "email": email},
    )
