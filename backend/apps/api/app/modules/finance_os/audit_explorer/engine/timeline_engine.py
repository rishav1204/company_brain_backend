from __future__ import annotations

from typing import Any

from app.modules.platform.governance.utils.object_ref import format_object_ref
from app.modules.finance_os.audit_explorer.repositories.timeline_repository import timeline_repository
from app.modules.finance_os.audit_explorer.repositories.evidence_repository import audit_evidence_repository
from app.modules.finance_os.audit_explorer.read_models import audit_read_models


OBJECT_TYPE_ALIASES = {
    "invoice": "invoice",
    "journal": "journal",
    "payment": "payment",
    "vendor": "vendor",
    "workflow": "workflow",
    "gst_return": "gst_return",
    "reconciliation": "reconciliation",
    "forecast": "forecast",
    "agent_execution": "agent_execution",
}


def parse_object_ref(object_ref: str | None) -> tuple[str | None, str | None, str | None]:
    if not object_ref or ":" not in object_ref:
        return None, None, object_ref
    parts = object_ref.split(":", 2)
    if len(parts) == 3:
        domain, entity_type, entity_id = parts
        return entity_type, entity_id, format_object_ref(domain, entity_type, entity_id)
    return None, None, object_ref


def resolve_object_from_envelope(envelope: dict) -> tuple[str, str, str | None]:
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    entity_type = (
        envelope.get("entity_type")
        or payload.get("entity_type")
        or payload.get("object_type")
    )
    entity_id = (
        envelope.get("entity_id")
        or payload.get("entity_id")
        or payload.get("object_id")
        or payload.get("invoice_id")
        or payload.get("journal_id")
        or payload.get("workflow_instance_id")
        or payload.get("execution_id")
    )
    object_ref = payload.get("object_ref") or envelope.get("object_ref")
    if not entity_type and object_ref:
        et, eid, _ = parse_object_ref(str(object_ref))
        entity_type = et
        entity_id = entity_id or eid
    if entity_type and entity_id:
        ot = OBJECT_TYPE_ALIASES.get(str(entity_type), str(entity_type))
        ref = object_ref or format_object_ref("erp", ot, str(entity_id))
        return ot, str(entity_id), str(ref)
    event_type = str(envelope.get("event_type", ""))
    if "workflow" in event_type and payload.get("workflow_instance_id"):
        wid = str(payload["workflow_instance_id"])
        return "workflow", wid, format_object_ref("workflow", "instance", wid)
    if payload.get("execution_id"):
        eid = str(payload["execution_id"])
        return "agent_execution", eid, format_object_ref("finance_os", "agent_execution", eid)
    return "unknown", str(envelope.get("event_id", "unknown")), None


def build_timeline(org_id: str, *, object_type: str, object_id: str, limit: int = 200) -> list[dict[str, Any]]:
    items = timeline_repository.list_for_object(org_id, object_type=object_type, object_id=object_id, limit=limit)
    if len(items) < 3:
        legacy = audit_read_models.entity_timeline(org_id, entity_type=object_type, entity_id=object_id, limit=limit)
        seen = {i.get("event_type") for i in items}
        for row in legacy:
            et = row.get("event_type") or row.get("action", "")
            if et in seen:
                continue
            items.append(
                {
                    "id": row.get("id"),
                    "object_type": object_type,
                    "object_id": object_id,
                    "event_type": et,
                    "actor_id": row.get("actor_id"),
                    "event_timestamp": row.get("created_at"),
                    "metadata": row.get("payload_jsonb") or row.get("payload") or {},
                    "object_ref": row.get("object_ref"),
                    "trace_id": row.get("trace_id"),
                    "source": "governance_audit_logs",
                }
            )
    items.sort(key=lambda x: str(x.get("event_timestamp") or ""))
    for entry in items:
        tid = entry.get("id")
        if tid and not str(tid).startswith("skipped"):
            entry["evidence"] = audit_evidence_repository.list_for_timeline(org_id, str(tid))
    return items


def correlate_by_trace(org_id: str, trace_id: str) -> list[dict[str, Any]]:
    materialized = timeline_repository.list_by_trace(org_id, trace_id=trace_id)
    if materialized:
        return materialized
    return audit_read_models.list_governance_logs(org_id, trace_id=trace_id, limit=100)
