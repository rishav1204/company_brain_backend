from __future__ import annotations

from app.services.event_bus import event_bus

INVOICE_EXTRACTED = "invoice.extracted"
INVOICE_PREDICTED = "invoice.predicted"
INVOICE_DUPLICATE_SCORED = "invoice.duplicate_detected"
INVOICE_ANOMALY_DETECTED = "invoice.anomaly_detected"
INVOICE_PIPELINE_COMPLETED = "invoice.pipeline.completed"


def emit_invoice_extracted(org_id: str, payload: dict) -> None:
    event_bus.publish(INVOICE_EXTRACTED, org_id=org_id, payload=payload)


def emit_invoice_predicted(org_id: str, payload: dict) -> None:
    event_bus.publish(INVOICE_PREDICTED, org_id=org_id, payload=payload)


def emit_duplicate_scored(org_id: str, payload: dict) -> None:
    event_bus.publish(INVOICE_DUPLICATE_SCORED, org_id=org_id, payload=payload)


def emit_anomaly_detected(org_id: str, payload: dict) -> None:
    event_bus.publish(INVOICE_ANOMALY_DETECTED, org_id=org_id, payload=payload)


def emit_pipeline_completed(org_id: str, payload: dict) -> None:
    event_bus.publish(INVOICE_PIPELINE_COMPLETED, org_id=org_id, payload=payload)
