from __future__ import annotations

from app.modules.finance_os.memory.memories import (
    accounting_memory,
    approval_memory,
    compliance_memory,
    reconciliation_memory,
    treasury_memory,
    user_preference_memory,
    vendor_memory,
)

EXTRACTOR_MAP: dict[str, list] = {
    "payment.executed": [vendor_memory],
    "erp.payment.completed": [vendor_memory],
    "approval.completed": [approval_memory],
    "approval.rejected": [approval_memory],
    "workflow.approved": [approval_memory],
    "workflow.intelligence.completed": [approval_memory],
    "invoice.predicted": [accounting_memory],
    "invoice.duplicate_detected": [vendor_memory],
    "invoice.anomaly_detected": [vendor_memory],
    "erp.invoice.approved": [vendor_memory],
    "journal.posted": [accounting_memory],
    "erp.journal.posted": [accounting_memory],
    "liquidity_alert.created": [treasury_memory],
    "cash.forecast.updated": [treasury_memory],
    "treasury.risk.detected": [treasury_memory],
    "compliance.alert.generated": [compliance_memory],
    "compliance.alert": [compliance_memory],
    "gst.mismatch.detected": [compliance_memory],
    "reconciliation.completed": [reconciliation_memory],
    "reconciliation.adjustment.posted": [reconciliation_memory],
    "decision.recorded": [user_preference_memory],
    "memory.write": [user_preference_memory],
}

NOISE_EVENTS = {
    "document.uploaded",
    "scheduler.tick",
    "audit.log.created",
}


def extract_from_event(event_type: str, payload: dict) -> dict | None:
    if event_type in NOISE_EVENTS:
        return None
    if payload.get("title") and payload.get("content"):
        return {
            "memory_type": payload.get("memory_type", "user"),
            "entity_type": payload.get("entity_type"),
            "entity_id": payload.get("entity_id"),
            "title": payload["title"],
            "content": payload["content"],
            "importance_score": float(payload.get("importance_score", 55)),
            "references": payload.get("references") or [],
            "ttl_policy": payload.get("ttl_policy", "90d"),
            "metadata": payload.get("metadata") or {},
        }
    extractors = EXTRACTOR_MAP.get(event_type, [])
    for extractor in extractors:
        result = extractor.extract(event_type, payload)
        if result:
            return result
    return None
