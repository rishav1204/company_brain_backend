from __future__ import annotations

from app.modules.platform.api_gateway.engine.webhook_dispatcher import dispatch_event

delivery_engine = type("DeliveryEngine", (), {"dispatch": staticmethod(dispatch_event)})()
