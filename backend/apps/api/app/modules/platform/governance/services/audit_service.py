from __future__ import annotations

import hashlib
from typing import Any

from app.modules.platform.governance.repositories.audit_repository import governance_audit_repository
from app.modules.platform.governance.utils.audit_context import skip_auto_audit
from app.modules.platform.governance.validators.audit_validator import validate_audit_entry
from app.services.logger import log_event
from app.services.metrics import metrics_store


def mask_sensitive_fields(payload: dict[str, Any]) -> dict[str, Any]:
    from app.modules.platform.governance.utils.field_crypto import encrypt_field

    sensitive_keys = {"pan", "aadhaar", "account_number", "bank_account", "ifsc", "password", "secret"}
    masked: dict[str, Any] = {}
    for key, value in payload.items():
        if str(key).lower() in sensitive_keys and value is not None:
            raw = str(value)
            masked[key] = encrypt_field(raw) if len(raw) > 8 else "***"
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_fields(value)
        else:
            masked[key] = value
    return masked


class AuditService:
    def schema_ready(self) -> bool:
        return governance_audit_repository.schema_ready()

    def record(
        self,
        *,
        org_id: str,
        actor_type: str,
        actor_id: str,
        action: str,
        object_ref: str,
        payload: dict | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        source_service: str | None = None,
        event_type: str | None = None,
        skip_auto_audit_flag: bool = False,
    ) -> dict[str, Any]:
        if skip_auto_audit_flag:
            skip_auto_audit()
        entry = {
            "action": action,
            "object_ref": object_ref,
            "entity_type": entity_type,
            "entity_id": entity_id,
        }
        validate_audit_entry(entry)
        safe_payload = mask_sensitive_fields(payload or {})
        row = governance_audit_repository.append(
            org_id=org_id,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type=event_type or action,
            object_ref=object_ref,
            payload_jsonb=safe_payload,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            request_id=request_id,
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
            source_service=source_service,
        )
        metrics_store.incr_governance_audit()
        log_event("governance.audit.recorded", org_id=org_id, action=action, object_ref=object_ref)
        try:
            from app.modules.platform.governance.events.audit_events import emit_audit_log_created

            emit_audit_log_created(org_id, audit_id=row.get("id", ""), action=action, object_ref=object_ref)
        except Exception:
            pass
        return row

    def record_legacy(
        self,
        org_id: str,
        actor_type: str,
        actor_id: str,
        event_type: str,
        object_ref: str,
        payload_jsonb: dict,
        **ctx: Any,
    ) -> dict[str, Any]:
        before_state = ctx.get("before_state")
        after_state = ctx.get("after_state")
        if before_state is None and isinstance(payload_jsonb.get("before"), dict):
            before_state = payload_jsonb.get("before")
        if after_state is None and isinstance(payload_jsonb.get("after"), dict):
            after_state = payload_jsonb.get("after")
        if before_state is None and "from" in payload_jsonb:
            before_state = {"status": payload_jsonb.get("from")}
        if after_state is None and "to" in payload_jsonb:
            after_state = {"status": payload_jsonb.get("to")}
        skip_auto_audit()
        return self.record(
            org_id=org_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=event_type,
            object_ref=object_ref,
            payload=payload_jsonb,
            event_type=event_type,
            entity_type=ctx.get("entity_type"),
            entity_id=ctx.get("entity_id"),
            before_state=before_state,
            after_state=after_state,
            request_id=ctx.get("request_id"),
            trace_id=ctx.get("trace_id"),
            ip_address=ctx.get("ip_address"),
            user_agent=ctx.get("user_agent"),
            source_service=ctx.get("source_service"),
        )

    def record_replay(
        self,
        org_id: str,
        *,
        actor_id: str,
        event_ids: list[str],
        event_type: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        row = self.record(
            org_id=org_id,
            actor_type="user",
            actor_id=actor_id,
            action="platform.event.replay",
            object_ref=f"platform:replay:{len(event_ids)}",
            payload={"event_ids": event_ids, "event_type_filter": event_type, "count": len(event_ids)},
            trace_id=trace_id,
            source_service="platform.events",
        )
        try:
            from app.modules.platform.governance.services.evidence_service import evidence_service

            for eid in event_ids[:50]:
                evidence_service.link(
                    org_id,
                    entity_type="audit_log",
                    entity_id=row.get("id", ""),
                    evidence_type="event",
                    evidence_ref=eid,
                    metadata={"link": "replay"},
                )
        except Exception:
            pass
        return row

    def list_logs(self, org_id: str, **filters: Any) -> list[dict[str, Any]]:
        return governance_audit_repository.list_logs(org_id, **filters)

    def entity_timeline(self, org_id: str, *, entity_type: str, entity_id: str, limit: int = 100) -> list[dict]:
        return self.list_logs(org_id, entity_type=entity_type, entity_id=entity_id, limit=limit)

    def persist_from_event_envelope(self, envelope: dict) -> dict[str, Any]:
        org_id = str(envelope.get("org_id", ""))
        event_type = str(envelope.get("event_type", ""))
        payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
        entity_type = envelope.get("entity_type") or payload.get("entity_type")
        entity_id = envelope.get("entity_id") or payload.get("entity_id")
        return self.record(
            org_id=org_id,
            actor_type="system",
            actor_id=str(envelope.get("actor_id") or envelope.get("source", "event_bus")),
            action=f"audit.persist.{event_type}",
            object_ref=f"event:{envelope.get('event_id', '')}",
            payload=envelope,
            entity_type=str(entity_type) if entity_type else None,
            entity_id=str(entity_id) if entity_id else None,
            trace_id=str(envelope.get("trace_id", "")) or None,
            source_service=str(envelope.get("source", "platform.events")),
            event_type=f"audit.persist.{event_type}",
        )

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


audit_service = AuditService()
