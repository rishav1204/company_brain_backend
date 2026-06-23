from datetime import datetime, timezone
from uuid import uuid4

from app.modules.platform.events.services.event_service import platform_event_service
from app.services.event_org_validation import require_org_id
from app.services.event_queue import event_queue
from app.services.event_topology import topic_for_event_type
from app.services.principal_context import build_principal


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventBus:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(
        self,
        event_type: str,
        org_id: str,
        source: str,
        trace_id: str,
        payload: dict,
        principal: dict | None = None,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        org_id = require_org_id(org_id, context="event_bus_publish")
        if platform_event_service.schema_ready():
            result = platform_event_service.publish(
                event_type=event_type,
                org_id=org_id,
                source=source,
                payload=payload,
                trace_id=trace_id or str(uuid4()),
                entity_type=entity_type or payload.get("entity_type"),
                entity_id=entity_id or payload.get("entity_id"),
                metadata=metadata,
                principal=principal,
                idempotency_key=idempotency_key,
            )
            event = result.get("envelope") or {}
            self.events.append(event)
            return event

        topic = topic_for_event_type(event_type)
        resolved_principal = principal
        if resolved_principal is None and isinstance(payload.get("principal"), dict):
            resolved_principal = payload.get("principal")
        if resolved_principal is None:
            resolved_principal = build_principal(user_id=source, roles=["system_worker"], attrs={})
        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "topic": topic,
            "org_id": org_id,
            "source": source,
            "occurred_at": now_iso(),
            "trace_id": trace_id,
            "principal": resolved_principal,
            "payload": payload,
            "schema_version": "v1",
        }
        self.events.append(event)
        event_queue.publish(event)
        from app.services.repositories import audit_repo

        audit_repo.create_log(
            org_id=org_id,
            actor_type="system",
            actor_id=source,
            event_type=event_type,
            object_ref=f"event:{event['event_id']}",
            payload_jsonb=event,
        )
        return event


event_bus = EventBus()
