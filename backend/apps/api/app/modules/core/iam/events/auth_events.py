from uuid import uuid4

from app.core.request_context import get_request_context
from app.services.event_bus import event_bus


def _resolve_trace_id() -> str:
    try:
        ctx = get_request_context()
        return ctx.trace_id or ctx.request_id
    except RuntimeError:
        return str(uuid4())


def emit_user_login(*, org_id: str, user_id: str, session_id: str) -> None:
    trace_id = _resolve_trace_id()
    event_bus.publish(
        event_type="user.login",
        org_id=org_id,
        source="iam",
        trace_id=trace_id,
        payload={"user_id": user_id, "session_id": session_id},
        principal={"user_id": user_id, "roles": ["system_worker"], "attrs": {}},
    )


def emit_user_logout(*, org_id: str, user_id: str, session_id: str) -> None:
    trace_id = _resolve_trace_id()
    event_bus.publish(
        event_type="user.logout",
        org_id=org_id,
        source="iam",
        trace_id=trace_id,
        payload={"user_id": user_id, "session_id": session_id},
        principal={"user_id": user_id, "roles": ["system_worker"], "attrs": {}},
    )
