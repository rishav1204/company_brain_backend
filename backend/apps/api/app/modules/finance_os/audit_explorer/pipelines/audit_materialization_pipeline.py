from __future__ import annotations

from datetime import datetime, timezone

from app.modules.finance_os.audit_explorer.engine.timeline_engine import resolve_object_from_envelope
from app.modules.finance_os.audit_explorer.repositories.timeline_repository import timeline_repository
from app.modules.finance_os.audit_explorer.repositories.evidence_repository import audit_evidence_repository
from app.modules.finance_os.audit_explorer.repositories.ai_decision_repository import ai_decision_repository
from app.modules.finance_os.audit_explorer.events.audit_explorer_events import (
    emit_timeline_updated,
    emit_evidence_linked,
    emit_ai_decision_recorded,
)
from app.modules.platform.governance.services.audit_service import audit_service


AI_EVENT_TYPES = frozenset(
    {
        "agent.completed",
        "agent.recommendation.created",
        "ai.decision.recorded",
        "invoice.ai.reviewed",
        "invoice.predicted",
        "invoice.extracted",
    }
)

MATERIALIZE_EVENT_TYPES = frozenset(
    {
        "audit.log.created",
        "invoice.created",
        "invoice.received",
        "invoice.approved",
        "invoice.ai.reviewed",
        "invoice.extracted",
        "invoice.predicted",
        "journal.posted",
        "journal.approved",
        "journal.reversed",
        "erp.journal.posted",
        "workflow.started",
        "workflow.approved",
        "workflow.completed",
        "approval.completed",
        "approval.rejected",
        "workflow.escalated",
        "workflow.step.completed",
        "agent.completed",
        "agent.recommendation.created",
        "ai.decision.recorded",
        "forecast.generated",
        "forecast.updated",
        "payment.executed",
        "payment.failed",
        "reconciliation.completed",
        "reconciliation.adjustment.posted",
        "gst.transaction.recorded",
        "erp.gst.return.generated",
        "compliance.alert.generated",
        "report.generated",
        "report.snapshot.created",
        "policy.evaluated",
        "policy.denied",
        "policy.approved",
        "policy.override.required",
        "policy.risk.detected",
        "consolidation.completed",
        "consolidation.failed",
        "elimination.generated",
        "intercompany.created",
        "intercompany.mismatch.detected",
        "entity.closed",
        "webhook.received",
        "webhook.delivered",
        "webhook.failed",
        "api.key.created",
        "api.key.revoked",
        "integration.connected",
    }
)


def _parse_timestamp(envelope: dict) -> datetime:
    for key in ("timestamp", "created_at", "event_timestamp"):
        val = envelope.get(key)
        if val:
            if isinstance(val, datetime):
                return val
            try:
                return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            except ValueError:
                pass
    return datetime.now(timezone.utc)


def _link_evidence_from_payload(org_id: str, timeline_id: str, payload: dict, trace_id: str | None) -> None:
    refs = payload.get("evidence_refs") or payload.get("evidence") or []
    if isinstance(refs, dict):
        refs = list(refs.values())
    for ref in refs[:20]:
        if not ref:
            continue
        etype = "document"
        if isinstance(ref, dict):
            etype = str(ref.get("type") or ref.get("evidence_type") or "document")
            ref_val = str(ref.get("ref") or ref.get("evidence_ref") or ref.get("id") or "")
        else:
            ref_val = str(ref)
        if not ref_val:
            continue
        row = audit_evidence_repository.link(
            org_id,
            timeline_id=timeline_id,
            evidence_type=etype,
            evidence_ref=ref_val,
        )
        if row.get("id"):
            emit_evidence_linked(org_id, timeline_id=timeline_id, evidence_type=etype, evidence_ref=ref_val, trace_id=trace_id)


def materialize_from_audit_log(org_id: str, payload: dict, trace_id: str | None = None) -> dict | None:
    audit_id = str(payload.get("audit_id") or "")
    action = str(payload.get("action") or "")
    object_ref = str(payload.get("object_ref") or "")
    if not audit_id:
        return None
    logs = audit_service.list_logs(org_id, limit=1)
    log_row = next((r for r in logs if str(r.get("id")) == audit_id), None)
    if not log_row:
        log_row = {
            "entity_type": payload.get("entity_type"),
            "entity_id": payload.get("entity_id"),
            "action": action,
            "object_ref": object_ref,
            "actor_id": payload.get("actor_id"),
            "trace_id": trace_id,
            "payload_jsonb": payload,
            "created_at": datetime.now(timezone.utc),
        }
    entity_type = log_row.get("entity_type") or "unknown"
    entity_id = log_row.get("entity_id") or audit_id
    return timeline_repository.upsert(
        org_id,
        object_type=str(entity_type),
        object_id=str(entity_id),
        event_type=str(log_row.get("event_type") or log_row.get("action") or action),
        actor_id=str(log_row.get("actor_id")) if log_row.get("actor_id") else None,
        event_timestamp=log_row.get("created_at"),
        metadata=log_row.get("payload_jsonb") or payload,
        source_audit_log_id=audit_id,
        trace_id=str(log_row.get("trace_id") or trace_id) if (log_row.get("trace_id") or trace_id) else None,
        object_ref=str(log_row.get("object_ref") or object_ref) or None,
    )


def materialize_from_envelope(envelope: dict) -> dict:
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return {"status": "skipped", "reason": "no_org"}
    event_type = str(envelope.get("event_type", ""))
    if event_type not in MATERIALIZE_EVENT_TYPES:
        return {"status": "skipped", "reason": "event_not_tracked"}
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    if event_type == "audit.log.created":
        row = materialize_from_audit_log(org_id, payload, trace_id=str(envelope.get("trace_id") or "") or None)
        if row and row.get("id"):
            emit_timeline_updated(
                org_id,
                timeline_id=str(row["id"]),
                object_type=str(row.get("object_type") or "unknown"),
                object_id=str(row.get("object_id") or ""),
                trace_id=str(envelope.get("trace_id") or "") or None,
            )
        return {"status": "ok", "timeline": row}

    object_type, object_id, object_ref = resolve_object_from_envelope(envelope)
    if object_type == "unknown":
        return {"status": "skipped", "reason": "unresolved_object"}

    actor_id = envelope.get("actor_id") or payload.get("actor_id") or payload.get("user_id")
    row = timeline_repository.upsert(
        org_id,
        object_type=object_type,
        object_id=object_id,
        event_type=event_type,
        actor_id=str(actor_id) if actor_id else None,
        event_timestamp=_parse_timestamp(envelope),
        metadata=payload,
        source_event_id=str(envelope.get("event_id") or "") or None,
        trace_id=str(envelope.get("trace_id") or "") or None,
        object_ref=object_ref,
    )
    if row.get("id") and not str(row["id"]).startswith("skipped"):
        emit_timeline_updated(
            org_id,
            timeline_id=str(row["id"]),
            object_type=object_type,
            object_id=object_id,
            trace_id=str(envelope.get("trace_id") or "") or None,
        )
        _link_evidence_from_payload(org_id, str(row["id"]), payload, str(envelope.get("trace_id") or "") or None)

    if event_type in AI_EVENT_TYPES:
        _materialize_ai_trail(org_id, envelope, object_type, object_id, payload)

    return {"status": "ok", "timeline": row}


def _materialize_ai_trail(org_id: str, envelope: dict, object_type: str, object_id: str, payload: dict) -> None:
    execution_id = str(
        payload.get("execution_id")
        or payload.get("agent_execution_id")
        or (object_id if object_type == "agent_execution" else "")
        or ""
    ) or None
    summary = str(
        payload.get("reasoning_summary")
        or payload.get("summary")
        or payload.get("recommendation")
        or envelope.get("event_type", "")
    )
    confidence = payload.get("confidence") or payload.get("confidence_score")
    try:
        conf = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        conf = None
    factors = {
        k: v
        for k, v in payload.items()
        if k not in {"prompt", "chain_of_thought", "raw_llm_output", "full_prompt"}
    }
    trail = ai_decision_repository.upsert(
        org_id,
        decision_type=str(payload.get("decision_type") or payload.get("recommendation_type") or "agent_recommendation"),
        reasoning_summary=summary,
        input_context=factors,
        agent_execution_id=execution_id,
        ai_trace_id=str(payload.get("ai_trace_id") or payload.get("trace_id") or "") or None,
        recommendation_id=str(payload.get("recommendation_id") or "") or None,
        confidence_score=conf,
        outcome=str(payload.get("status") or payload.get("outcome") or "proposed"),
        approved_by=str(payload.get("approved_by") or "") or None,
    )
    if trail.get("id"):
        emit_ai_decision_recorded(org_id, trail_id=str(trail["id"]), execution_id=execution_id, trace_id=str(envelope.get("trace_id") or "") or None)


def run_refresh_object(org_id: str, *, object_type: str, object_id: str) -> dict:
    logs = audit_service.list_logs(org_id, entity_type=object_type, entity_id=object_id, limit=500)
    count = 0
    for log in logs:
        row = timeline_repository.upsert(
            org_id,
            object_type=object_type,
            object_id=object_id,
            event_type=str(log.get("event_type") or log.get("action") or "audit.event"),
            actor_id=str(log.get("actor_id")) if log.get("actor_id") else None,
            event_timestamp=log.get("created_at"),
            metadata=log.get("payload_jsonb") or {},
            source_audit_log_id=str(log.get("id")) if log.get("id") else None,
            trace_id=str(log.get("trace_id")) if log.get("trace_id") else None,
            object_ref=str(log.get("object_ref")) if log.get("object_ref") else None,
        )
        if row.get("id"):
            count += 1
    return {"status": "ok", "object_type": object_type, "object_id": object_id, "materialized": count}


def run_backfill(org_id: str, *, limit: int = 1000) -> dict:
    logs = audit_service.list_logs(org_id, limit=limit)
    count = 0
    for log in logs:
        et = log.get("entity_type") or "unknown"
        eid = log.get("entity_id") or log.get("id")
        if not eid:
            continue
        row = timeline_repository.upsert(
            org_id,
            object_type=str(et),
            object_id=str(eid),
            event_type=str(log.get("event_type") or log.get("action") or "audit.event"),
            actor_id=str(log.get("actor_id")) if log.get("actor_id") else None,
            event_timestamp=log.get("created_at"),
            metadata=log.get("payload_jsonb") or {},
            source_audit_log_id=str(log.get("id")) if log.get("id") else None,
            trace_id=str(log.get("trace_id")) if log.get("trace_id") else None,
            object_ref=str(log.get("object_ref")) if log.get("object_ref") else None,
        )
        if row.get("id"):
            count += 1
    return {"status": "ok", "materialized": count}
