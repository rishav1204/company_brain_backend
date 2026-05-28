from __future__ import annotations

from app.modules.platform.notifications.realtime.channel_manager import channel_manager
from app.modules.workflows.services.realtime_hub import workflow_realtime_hub


class EventStreamDispatcher:
    def publish(self, org_id: str, event: dict, *, channel: str = "action_center") -> None:
        normalized = channel_manager.normalize(channel)
        payload = {**event, "channel": normalized}
        workflow_realtime_hub.publish(org_id, payload)

    def since(self, org_id: str, cursor: int = 0, *, channel: str | None = None) -> tuple[list[dict], int]:
        events, next_cursor = workflow_realtime_hub.since(org_id, cursor)
        return channel_manager.filter_events(events, channel), next_cursor


event_stream_dispatcher = EventStreamDispatcher()
