from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.modules.platform.events.bus.event_registry import validate_event_owner
from app.modules.platform.events.queues.queue_manager import queue_manager
from app.modules.platform.events.repositories.event_repository import event_repository
from app.modules.platform.events.repositories.queue_repository import queue_repository
from app.modules.platform.events.schemas.event_schema import CanonicalEventEnvelope
from app.modules.platform.events.services.idempotency_service import platform_idempotency_service
from app.modules.platform.events.middleware.event_trace_middleware import trace_event_processing
from app.modules.platform.events.services.rate_limit_service import event_rate_limit_service
from app.modules.platform.events.validators.event_validator import validate_event_envelope
from app.services.event_topology import route_for_envelope, topic_for_event_type
from app.services.principal_context import build_principal
from app.services.repositories import audit_repo


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlatformEventService:
    def schema_ready(self) -> bool:
        return event_repository.schema_ready()

    def publish(
        self,
        *,
        event_type: str,
        org_id: str,
        source: str,
        payload: dict[str, Any],
        trace_id: str | None = None,
        actor_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        metadata: dict | None = None,
        principal: dict | None = None,
        idempotency_key: str | None = None,
        idempotency_scope: str = "event_publish",
    ) -> dict[str, Any]:
        if not validate_event_owner(event_type, source):
            raise PermissionError(f"Source {source} is not owner for event {event_type}")

        allowed, deny = event_rate_limit_service.allow_publish(org_id)
        if not allowed:
            from app.modules.platform.events.events.system_events import emit_queue_blocked

            emit_queue_blocked(org_id, queue="publish", reason=deny or "rate_limited")
            raise PermissionError(deny or "Event publish rate limit exceeded")

        request_body = {
            "event_type": event_type,
            "org_id": org_id,
            "source": source,
            "payload": payload,
            "entity_type": entity_type,
            "entity_id": entity_id,
        }
        if idempotency_key:
            replay, cached = platform_idempotency_service.check_and_store(
                org_id, idempotency_scope, idempotency_key, request_payload=request_body
            )
            if replay and cached:
                return cached

        event_id = str(uuid4())
        resolved_principal = principal
        if resolved_principal is None and isinstance(payload.get("principal"), dict):
            resolved_principal = payload["principal"]
        if resolved_principal is None:
            resolved_principal = build_principal(user_id=actor_id or source, roles=["system_worker"], attrs={})

        envelope_model = CanonicalEventEnvelope(
            event_id=event_id,
            event_type=event_type,
            event_version="v1",
            org_id=org_id,
            entity_type=entity_type or payload.get("entity_type"),
            entity_id=entity_id or payload.get("entity_id"),
            source=source,
            timestamp=_now_iso(),
            trace_id=trace_id or str(uuid4()),
            actor_id=actor_id or payload.get("actor_id"),
            payload=payload,
            metadata=metadata or {},
            topic=topic_for_event_type(event_type),
            principal=resolved_principal,
        )
        bus_envelope = envelope_model.to_bus_dict()
        validate_event_envelope(bus_envelope)
        queue = route_for_envelope(bus_envelope)

        with trace_event_processing(event_type, queue):
            if event_repository.schema_ready():
                event_repository.append(
                    org_id=org_id,
                    event_id=event_id,
                    event_type=event_type,
                    source=source,
                    payload=payload,
                    metadata=metadata,
                    entity_type=entity_type,
                    trace_id=envelope_model.trace_id,
                    actor_id=actor_id,
                )

            if queue_repository and event_repository.schema_ready():
                try:
                    queue_repository.create_job(
                        org_id=org_id,
                        queue_name=queue,
                        job_type="event_publish",
                        payload={"event_id": event_id, "event_type": event_type},
                        event_id=event_id,
                    )
                except Exception:
                    pass

            result = queue_manager.publish(bus_envelope)
            try:
                from app.modules.platform.events.services.webhook_service import webhook_service

                webhook_service.dispatch_event(org_id, event_type, bus_envelope)
            except Exception:
                pass
            try:
                # Module 7 integrations webhooks (new)
                from app.modules.platform.integrations.services.webhook_service import integrations_webhook_service

                integrations_webhook_service.dispatch_event(org_id, event_type, bus_envelope)
            except Exception:
                pass
            try:
                from app.modules.platform.events.services.realtime_bridge import platform_realtime_bridge

                platform_realtime_bridge.push(org_id, event_type, bus_envelope)
            except Exception:
                pass
            audit_repo.create_log(
                org_id=org_id,
                actor_type="system",
                actor_id=source,
                event_type=event_type,
                object_ref=f"event:{event_id}",
                payload_jsonb=bus_envelope,
            )

        response = {
            "event_id": event_id,
            "event_type": event_type,
            "queue": result.queue,
            "queue_status": result.status,
            "envelope": bus_envelope,
        }
        if idempotency_key:
            platform_idempotency_service.store(
                org_id,
                idempotency_scope,
                idempotency_key,
                request_payload=request_body,
                response_payload=response,
            )
        return response

    def replay(
        self,
        org_id: str,
        *,
        event_type: str | None = None,
        limit: int = 50,
        actor_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[dict]:
        if not event_repository.schema_ready():
            return []
        rows = event_repository.list_events(org_id, event_type=event_type, limit=limit)
        replayed: list[dict] = []
        event_ids: list[str] = []
        for row in rows:
            envelope = {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "org_id": org_id,
                "source": row["source"],
                "occurred_at": row["created_at"].isoformat() if row.get("created_at") else _now_iso(),
                "trace_id": row.get("trace_id") or trace_id or "",
                "payload": row.get("payload") or {},
                "schema_version": "v1",
                "_replay": True,
            }
            queue_manager.publish(envelope)
            replayed.append(envelope)
            event_ids.append(str(row["event_id"]))
        if event_ids and actor_id:
            try:
                from app.modules.platform.governance.services.audit_service import audit_service
                from app.services.metrics import metrics_store

                audit_service.record_replay(
                    org_id,
                    actor_id=actor_id,
                    event_ids=event_ids,
                    event_type=event_type,
                    trace_id=trace_id,
                )
                metrics_store.incr_governance_replay()
            except Exception:
                pass
        return replayed

    def mark_processed(self, org_id: str, event_id: str) -> None:
        if event_repository.schema_ready():
            event_repository.mark_processed(org_id, event_id)


platform_event_service = PlatformEventService()
