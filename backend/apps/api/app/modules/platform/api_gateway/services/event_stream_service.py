from __future__ import annotations

from app.modules.platform.events.bus.event_registry import ALL_EVENTS
from app.modules.platform.events.repositories.event_repository import event_repository
from app.modules.platform.api_gateway.schemas.scope_catalog import PARTNER_SUBSCRIBABLE_EVENTS


class EventStreamService:
    def list_partner_catalog(self) -> list[dict]:
        out = []
        for ev in ALL_EVENTS.values():
            if ev.event_type in PARTNER_SUBSCRIBABLE_EVENTS:
                out.append(
                    {
                        "event_type": ev.event_type,
                        "owner": ev.owner,
                        "category": ev.category,
                    }
                )
        return sorted(out, key=lambda x: x["event_type"])

    def list_events(
        self,
        org_id: str,
        *,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        if not event_repository.schema_ready():
            return []
        return event_repository.list_for_org(org_id, event_type=event_type, limit=limit)

    def get_event(self, org_id: str, event_id: str) -> dict | None:
        if not event_repository.schema_ready():
            return None
        return event_repository.get_by_event_id(org_id, event_id)


event_stream_service = EventStreamService()
