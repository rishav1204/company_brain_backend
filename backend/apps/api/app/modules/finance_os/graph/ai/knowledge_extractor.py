from __future__ import annotations

from app.modules.finance_os.graph.extractors import (
    asset_extractor,
    compliance_extractor,
    invoice_extractor,
    journal_extractor,
    payment_extractor,
    reconciliation_extractor,
    treasury_extractor,
    workflow_extractor,
)

EXTRACTOR_MAP: dict[str, list] = {
    "erp.invoice.created": [invoice_extractor],
    "invoice.created": [invoice_extractor],
    "invoice.received": [invoice_extractor],
    "erp.invoice.approved": [invoice_extractor, workflow_extractor],
    "approval.requested": [invoice_extractor, workflow_extractor],
    "approval.completed": [workflow_extractor],
    "approval.rejected": [workflow_extractor],
    "workflow.completed": [workflow_extractor],
    "workflow.stage.completed": [workflow_extractor],
    "workflow.failed": [workflow_extractor],
    "sla.breached": [workflow_extractor],
    "journal.posted": [journal_extractor],
    "erp.journal.posted": [journal_extractor],
    "payment.executed": [payment_extractor, treasury_extractor],
    "erp.payment.completed": [payment_extractor, treasury_extractor],
    "bank.transaction.imported": [treasury_extractor],
    "bank.statement.imported": [treasury_extractor],
    "reconciliation.completed": [reconciliation_extractor],
    "reconciliation.adjustment.posted": [reconciliation_extractor],
    "erp.gst.return.generated": [compliance_extractor],
    "gst.transaction.recorded": [compliance_extractor],
    "compliance.completed": [compliance_extractor],
    "irn.generated": [compliance_extractor],
    "invoice.anomaly_detected": [invoice_extractor],
    "liquidity_alert.created": [treasury_extractor],
    "decision.recorded": [invoice_extractor],
}

NOISE_EVENTS = {"document.uploaded", "scheduler.tick", "audit.log.created"}


def extract_from_event(event_type: str, payload: dict) -> dict | None:
    if event_type in NOISE_EVENTS:
        return None
    if payload.get("nodes") is not None and payload.get("edges") is not None:
        return {
            "nodes": payload["nodes"],
            "edges": payload["edges"],
            "entity_type": payload.get("entity_type"),
            "entity_id": payload.get("entity_id"),
        }
    extractors = EXTRACTOR_MAP.get(event_type, [])
    merged_nodes: list[dict] = []
    merged_edges: list[dict] = []
    entity_type = None
    entity_id = None
    for extractor in extractors:
        result = extractor.extract(event_type, payload)
        if not result:
            continue
        merged_nodes.extend(result.get("nodes") or [])
        merged_edges.extend(result.get("edges") or [])
        entity_type = entity_type or result.get("entity_type")
        entity_id = entity_id or result.get("entity_id")
    if not merged_nodes and not merged_edges:
        return None
    return {
        "nodes": merged_nodes,
        "edges": merged_edges,
        "entity_type": entity_type,
        "entity_id": entity_id,
    }
