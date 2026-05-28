from app.modules.platform.notifications.services.event_router import resolve_notification_plan


def test_approval_requested_maps() -> None:
    plan = resolve_notification_plan("approval.requested")
    assert plan is not None
    assert plan[0] == "approval_request"
    assert "email" in plan[2]
