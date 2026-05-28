from __future__ import annotations

ACTION_CENTER_CHANNELS = (
    "workflow_updates",
    "approval_queue",
    "risk_alerts",
    "compliance_alerts",
    "payment_updates",
    "action_center",
)


class ChannelManager:
    def normalize(self, channel_key: str) -> str:
        key = channel_key.strip().lower()
        if key in ACTION_CENTER_CHANNELS:
            return key
        return "action_center"

    def filter_events(self, events: list[dict], channel_key: str | None) -> list[dict]:
        if not channel_key or channel_key == "action_center":
            return events
        return [e for e in events if e.get("channel") == channel_key or channel_key in str(e.get("event_type", ""))]


channel_manager = ChannelManager()
