"""Platform event bus — canonical publish entry for new code."""

from app.modules.platform.events.services.event_service import platform_event_service
from app.services.event_bus import EventBus, event_bus as legacy_event_bus

__all__ = ["PlatformEventBus", "platform_event_bus", "legacy_event_bus"]


class PlatformEventBus:
    def publish(self, **kwargs):
        return platform_event_service.publish(**kwargs)


platform_event_bus = PlatformEventBus()
