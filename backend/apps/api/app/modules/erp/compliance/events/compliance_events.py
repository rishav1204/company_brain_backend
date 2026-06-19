from __future__ import annotations

from typing import Any

from app.modules.platform.events.services.event_service import platform_event_service


def emit_compliance_due(org_id: str, *, obligation_id: str, summary: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="compliance.due",
        org_id=org_id,
        source="erp.compliance",
        entity_type="compliance_obligation",
        entity_id=obligation_id,
        payload={"obligation_id": obligation_id, "summary": summary},
        trace_id=trace_id,
    )


def emit_compliance_overdue(org_id: str, *, obligation_id: str, summary: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="compliance.overdue",
        org_id=org_id,
        source="erp.compliance",
        entity_type="compliance_obligation",
        entity_id=obligation_id,
        payload={"obligation_id": obligation_id, "summary": summary},
        trace_id=trace_id,
    )


def emit_compliance_completed(org_id: str, *, obligation_id: str, compliance_code: str, return_period: str | None = None, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="compliance.completed",
        org_id=org_id,
        source="erp.compliance",
        entity_type="compliance_obligation",
        entity_id=obligation_id,
        payload={"obligation_id": obligation_id, "compliance_code": compliance_code, "return_period": return_period},
        trace_id=trace_id,
    )


def emit_compliance_escalated(org_id: str, *, obligation_id: str, level: int, role: str | None, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="compliance.escalated",
        org_id=org_id,
        source="erp.compliance",
        entity_type="compliance_obligation",
        entity_id=obligation_id,
        payload={"obligation_id": obligation_id, "escalation_level": level, "escalated_to_role": role},
        trace_id=trace_id,
    )


def emit_compliance_obligation_created(org_id: str, *, obligation_id: str, compliance_code: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="compliance.obligation.created",
        org_id=org_id,
        source="erp.compliance",
        entity_type="compliance_obligation",
        entity_id=obligation_id,
        payload={"obligation_id": obligation_id, "compliance_code": compliance_code},
        trace_id=trace_id,
    )
