"""Event consumer facade — re-exports handlers for backward compatibility."""
from __future__ import annotations

import app.services.event_consumers_handlers as _handlers
from app.services.event_consumers_router import consume_event

for _name in dir(_handlers):
    if _name.startswith("_") and not _name.startswith("__"):
        globals()[_name] = getattr(_handlers, _name)

__all__ = ["consume_event"]
