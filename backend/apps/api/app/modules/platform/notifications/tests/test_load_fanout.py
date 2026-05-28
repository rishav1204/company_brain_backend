from app.modules.platform.notifications.realtime.channel_manager import channel_manager


def test_channel_filter_fanout() -> None:
    events = [
        {"event_type": "notification.approval_request", "channel": "approval_queue", "toast": True},
        {"event_type": "workflow.started", "channel": "workflow_updates"},
    ]
    filtered = channel_manager.filter_events(events, "approval_queue")
    assert len(filtered) == 1
