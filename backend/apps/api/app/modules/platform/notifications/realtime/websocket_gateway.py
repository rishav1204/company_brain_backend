"""SSE gateway — reuses workflow realtime hub (WebSocket upgrade deferred to frontend)."""

from app.modules.platform.notifications.realtime.event_stream_dispatcher import event_stream_dispatcher

__all__ = ["event_stream_dispatcher"]
