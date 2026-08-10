from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.modules.platform.events.bus.event_registry import get_event_definition, validate_event_owner
from app.modules.platform.events.governance.financial_contracts import (
    is_financial_event_type,
    ordering_key as build_ordering_key,
    partition_key as build_partition_key,
    require_financial_registered,
)
from app.modules.platform.events.queues.queue_manager import queue_manager
from app.modules.platform.events.repositories.event_repository import event_repository
from app.modules.platform.events.repositories.outbox_repository import outbox_repository
from app.modules.platform.events.repositories.queue_repository import queue_repository
from app.modules.platform.events.schemas.event_schema import CanonicalEventEnvelope
from app.modules.platform.events.services.idempotency_service import platform_idempotency_service
from app.modules.platform.events.middleware.event_trace_middleware import trace_event_processing
from app.modules.platform.events.services.rate_limit_service import event_rate_limit_service
from app.modules.platform.events.validators.event_validator import validate_event_envelope
from app.services.event_org_validation import require_org_id
from app.services.event_topology import route_for_envelope, topic_for_event_type
from app.services.principal_context import build_principal
from app.services.repositories import audit_repo


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_event_version(event_type: str, metadata: dict | None) -> str:
    if metadata and metadata.get("event_version"):
        return str(metadata["event_version"])
    definition = get_event_definition(event_type)
    if definition and definition.version:
        return definition.version
    return "v1"


class PlatformEventService:
    def schema_ready(self) -> bool:
        return event_repository.schema_ready()

    def _build_envelope(
        self,
        *,
        event_id: str,
        event_type: str,
        org_id: str,
        source: str,
        payload: dict[str, Any],
        trace_id: str | None,
        actor_id: str | None,
        entity_type: str | None,
        entity_id: str | None,
        metadata: dict | None,
        principal: dict | None,
        correlation_id: str | None = None,
        request_id: str | None = None,
        company_id: str | None = None,
    ) -> tuple[CanonicalEventEnvelope, dict[str, Any], str]:
        resolved_principal = principal
        if resolved_principal is None and isinstance(payload.get("principal"), dict):
            resolved_principal = payload["principal"]
        if resolved_principal is None:
            resolved_principal = build_principal(user_id=actor_id or source, roles=["system_worker"], attrs={})

        et = entity_type or payload.get("entity_type")
        eid = entity_id or payload.get("entity_id")
        event_version = _resolve_event_version(event_type, metadata)
        financial = is_financial_event_type(event_type)
        okey = build_ordering_key(entity_type=et, entity_id=eid, event_type=event_type)
        pkey = build_partition_key(org_id=org_id, entity_id=str(eid) if eid else None)
        meta = dict(metadata or {})
        meta.setdefault("is_financial", financial)
        if okey:
            meta.setdefault("ordering_key", okey)
        if pkey:
            meta.setdefault("partition_key", pkey)
        if correlation_id:
            meta.setdefault("correlation_id", correlation_id)
        if request_id:
            meta.setdefault("request_id", request_id)
        if company_id:
            meta.setdefault("company_id", company_id)

        envelope_model = CanonicalEventEnvelope(
            event_id=event_id,
            event_type=event_type,
            event_version=event_version,
            org_id=org_id,
            entity_type=et,
            entity_id=eid,
            source=source,
            timestamp=_now_iso(),
            trace_id=trace_id or str(uuid4()),
            actor_id=actor_id or payload.get("actor_id"),
            payload=payload,
            metadata=meta,
            topic=topic_for_event_type(event_type),
            principal=resolved_principal,
            correlation_id=correlation_id or meta.get("correlation_id"),
            request_id=request_id or meta.get("request_id"),
            company_id=company_id or meta.get("company_id"),
            partition_key=pkey,
            ordering_key=okey,
            is_financial=financial,
        )
        bus_envelope = envelope_model.to_bus_dict()
        validate_event_envelope(bus_envelope)
        queue = route_for_envelope(bus_envelope)
        return envelope_model, bus_envelope, queue

    def _side_effects(
        self,
        *,
        org_id: str,
        event_type: str,
        event_id: str,
        source: str,
        bus_envelope: dict,
        dual_write: bool,
    ) -> Any:
        """
        After outbox/log commit: optional legacy XADD, webhooks, realtime, audit.
        When outbox is ready, Redis stream publish is worker-driven unless dual_write is on.
        """

        class _Stub:
            queue = "outbox"
            status = "queued_outbox"

        result: Any = _Stub()
        if dual_write or not outbox_repository.schema_ready():
            result = queue_manager.publish(bus_envelope)
        try:
            from app.modules.platform.api_gateway.engine.webhook_dispatcher import dispatch_event

            dispatch_event(org_id, event_type, bus_envelope)
        except Exception:
            pass
        try:
            from app.modules.platform.events.services.realtime_bridge import platform_realtime_bridge

            platform_realtime_bridge.push(org_id, event_type, bus_envelope)
        except Exception:
            pass
        try:
            audit_repo.create_log(
                org_id=org_id,
                actor_type="system",
                actor_id=source,
                event_type=event_type,
                object_ref=f"event:{event_id}",
                payload_jsonb=bus_envelope,
            )
        except Exception:
            pass
        return result

    def publish_with_conn(
        self,
        conn,
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
        correlation_id: str | None = None,
        request_id: str | None = None,
        company_id: str | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Same-transaction path: append event log + outbox on the caller's connection.
        Caller MUST commit. Does not XADD to Redis (outbox publisher after commit).
        """
        org_id = require_org_id(org_id, context="platform_event_publish_tx")
        if not validate_event_owner(event_type, source):
            raise PermissionError(f"Source {source} is not owner for event {event_type}")
        require_financial_registered(event_type)

        event_id = event_id or str(uuid4())
        envelope_model, bus_envelope, queue = self._build_envelope(
            event_id=event_id,
            event_type=event_type,
            org_id=org_id,
            source=source,
            payload=payload,
            trace_id=trace_id,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
            principal=principal,
            correlation_id=correlation_id,
            request_id=request_id,
            company_id=company_id,
        )
        if event_repository.schema_ready():
            event_repository.append_with_conn(
                conn,
                org_id=org_id,
                event_id=event_id,
                event_type=event_type,
                source=source,
                payload=payload,
                metadata=metadata,
                entity_type=entity_type,
                entity_id=entity_id,
                trace_id=envelope_model.trace_id,
                actor_id=actor_id,
            )
        if outbox_repository.schema_ready():
            outbox_repository.enqueue_with_conn(
                conn,
                org_id=org_id,
                event_id=event_id,
                queue_name=queue,
                envelope=bus_envelope,
                event_type=event_type,
                event_version=envelope_model.event_version,
                correlation_id=envelope_model.correlation_id,
                request_id=envelope_model.request_id,
                company_id=envelope_model.company_id,
                actor_id=actor_id or envelope_model.actor_id,
                partition_key=envelope_model.partition_key,
                ordering_key=envelope_model.ordering_key,
                is_financial=bool(envelope_model.is_financial),
            )
        return {
            "event_id": event_id,
            "event_type": event_type,
            "queue": queue,
            "queue_status": "outbox_pending",
            "envelope": bus_envelope,
            "transactional": True,
        }

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
        correlation_id: str | None = None,
        request_id: str | None = None,
        company_id: str | None = None,
    ) -> dict[str, Any]:
        org_id = require_org_id(org_id, context="platform_event_publish")
        if not validate_event_owner(event_type, source):
            raise PermissionError(f"Source {source} is not owner for event {event_type}")
        require_financial_registered(event_type)

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
        envelope_model, bus_envelope, queue = self._build_envelope(
            event_id=event_id,
            event_type=event_type,
            org_id=org_id,
            source=source,
            payload=payload,
            trace_id=trace_id,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
            principal=principal,
            correlation_id=correlation_id,
            request_id=request_id,
            company_id=company_id,
        )

        dual_write = bool(getattr(settings, "event_outbox_dual_write", False))
        with trace_event_processing(event_type, queue):
            if event_repository.schema_ready():
                from app.services.db import get_db_conn, set_rls_org

                with get_db_conn() as conn:
                    set_rls_org(conn, org_id)
                    event_repository.append_with_conn(
                        conn,
                        org_id=org_id,
                        event_id=event_id,
                        event_type=event_type,
                        source=source,
                        payload=payload,
                        metadata=metadata,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        trace_id=envelope_model.trace_id,
                        actor_id=actor_id,
                    )
                    if outbox_repository.schema_ready():
                        outbox_repository.enqueue_with_conn(
                            conn,
                            org_id=org_id,
                            event_id=event_id,
                            queue_name=queue,
                            envelope=bus_envelope,
                            event_type=event_type,
                            event_version=envelope_model.event_version,
                            correlation_id=envelope_model.correlation_id,
                            request_id=envelope_model.request_id,
                            company_id=envelope_model.company_id,
                            actor_id=actor_id or envelope_model.actor_id,
                            partition_key=envelope_model.partition_key,
                            ordering_key=envelope_model.ordering_key,
                            is_financial=bool(envelope_model.is_financial),
                        )
                    conn.commit()

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

            # Wave 2: when outbox schema is ready, Redis XADD is worker-only by default.
            # Set EVENT_OUTBOX_DUAL_WRITE=true only for legacy low-latency dual-write.
            result = self._side_effects(
                org_id=org_id,
                event_type=event_type,
                event_id=event_id,
                source=source,
                bus_envelope=bus_envelope,
                dual_write=dual_write,
            )

        response = {
            "event_id": event_id,
            "event_type": event_type,
            "queue": getattr(result, "queue", queue),
            "queue_status": getattr(result, "status", "queued_outbox"),
            "envelope": bus_envelope,
            "outbox": outbox_repository.schema_ready() and not dual_write,
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
        from_event_id: str | None = None,
        actor_id: str | None = None,
        trace_id: str | None = None,
        via_outbox: bool | None = None,
        correlation_id: str | None = None,
        entity_id: str | None = None,
    ) -> list[dict]:
        """
        Operator replay from durable event log.
        Default Wave 2 path: re-enqueue through transactional outbox when ready.
        """
        if not event_repository.schema_ready():
            return []
        rows = event_repository.list_events(
            org_id,
            event_type=event_type,
            limit=limit,
            from_event_id=from_event_id,
        )
        use_outbox = bool(outbox_repository.schema_ready()) if via_outbox is None else bool(via_outbox)
        replayed: list[dict] = []
        event_ids: list[str] = []

        for row in rows:
            row_payload = row.get("payload") or {}
            if entity_id and str(row_payload.get("entity_id") or row.get("entity_id") or "") != str(entity_id):
                continue
            if correlation_id:
                meta = row_payload.get("metadata") if isinstance(row_payload, dict) else {}
                cid = ""
                if isinstance(meta, dict):
                    cid = str(meta.get("correlation_id") or "")
                if cid != str(correlation_id):
                    continue

            original_event_id = str(row["event_id"])
            new_event_id = str(uuid4())
            envelope = {
                "event_id": new_event_id,
                "event_type": row["event_type"],
                "org_id": org_id,
                "source": row["source"],
                "occurred_at": row["created_at"].isoformat() if row.get("created_at") else _now_iso(),
                "trace_id": row.get("trace_id") or trace_id or "",
                "payload": row_payload,
                "schema_version": "v1",
                "_replay": True,
                "_replay_of": original_event_id,
                "metadata": {
                    "replay": True,
                    "original_event_id": original_event_id,
                    "actor_id": actor_id,
                    "correlation_id": correlation_id,
                },
            }
            if use_outbox:
                from app.services.db import get_db_conn, set_rls_org

                q = route_for_envelope(envelope)
                with get_db_conn() as conn:
                    set_rls_org(conn, org_id)
                    outbox_repository.reenqueue_for_replay_with_conn(
                        conn,
                        org_id=org_id,
                        event_id=new_event_id,
                        queue_name=q,
                        envelope=envelope,
                        event_type=str(row["event_type"]),
                        event_version="v1",
                        correlation_id=correlation_id,
                        actor_id=actor_id,
                        is_financial=is_financial_event_type(str(row["event_type"])),
                    )
                    conn.commit()
            else:
                queue_manager.publish(envelope)
            replayed.append(envelope)
            event_ids.append(original_event_id)

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
