from __future__ import annotations

from app.services.event_consumers import _consume_notification_event


def process_notification_event(envelope: dict) -> None:
    _consume_notification_event(envelope)
