from __future__ import annotations

from typing import Any

from app.modules.workflows.services.workflow_service import workflow_service

_ENTITY_WORKFLOW_MAP = {
    "invoice": "AP_INVOICE_APPROVAL",
    "payment": "PAYMENT_APPROVAL",
    "journal": "JOURNAL_APPROVAL",
    "gst_return": "GST_FILING",
    "reconciliation": "BANK_RECONCILIATION",
    "vendor": "VENDOR_ONBOARDING",
}


def handle_entity_created(*, org_id: str, payload: dict[str, Any], trace_id: str | None = None) -> dict | None:
    if not workflow_service.schema_ready():
        return None
    entity_type = str(payload.get("entity_type") or payload.get("object_type") or "invoice")
    entity_id = str(payload.get("entity_id") or payload.get("object_id") or "")
    workflow_key = str(payload.get("workflow_key") or _ENTITY_WORKFLOW_MAP.get(entity_type, "AP_INVOICE_APPROVAL"))
    metadata = {
        "amount": payload.get("amount"),
        "vendor_risk": payload.get("vendor_risk"),
        "source_event": payload.get("event") or "entity.created",
    }
    if payload.get("metadata") and isinstance(payload["metadata"], dict):
        metadata.update(payload["metadata"])
    return workflow_service.start_workflow(
        org_id=org_id,
        user_id=str(payload.get("started_by") or payload.get("user_id") or ""),
        workflow_key=workflow_key,
        entity_type=entity_type,
        entity_id=entity_id or None,
        metadata=metadata,
        trace_id=trace_id,
    )
