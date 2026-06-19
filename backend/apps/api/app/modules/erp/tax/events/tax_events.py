from __future__ import annotations

from typing import Any

from app.modules.platform.events.services.event_service import platform_event_service


def emit_gst_transaction_recorded(
    org_id: str,
    *,
    gst_transaction_id: str,
    source_type: str,
    source_id: str,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="gst.transaction.recorded",
        org_id=org_id,
        source="erp.tax",
        entity_type="gst_transaction",
        entity_id=gst_transaction_id,
        payload={
            "gst_transaction_id": gst_transaction_id,
            "source_type": source_type,
            "source_id": source_id,
        },
        trace_id=trace_id,
    )


def emit_gst_mismatch_detected(
    org_id: str,
    *,
    reconciliation_id: str,
    summary: str,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="gst.mismatch.detected",
        org_id=org_id,
        source="erp.tax",
        entity_type="gst_reconciliation",
        entity_id=reconciliation_id,
        payload={"reconciliation_id": reconciliation_id, "summary": summary},
        trace_id=trace_id,
    )


def emit_tds_calculated(
    org_id: str,
    *,
    tds_transaction_id: str,
    section_code: str,
    tds_amount: float,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="tds.calculated",
        org_id=org_id,
        source="erp.tax",
        entity_type="tds_transaction",
        entity_id=tds_transaction_id,
        payload={
            "tds_transaction_id": tds_transaction_id,
            "section_code": section_code,
            "tds_amount": tds_amount,
        },
        trace_id=trace_id,
    )


def emit_irn_generated(
    org_id: str,
    *,
    e_invoice_id: str,
    irn: str,
    ar_invoice_id: str,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="irn.generated",
        org_id=org_id,
        source="erp.tax",
        entity_type="e_invoice",
        entity_id=e_invoice_id,
        payload={"e_invoice_id": e_invoice_id, "irn": irn, "ar_invoice_id": ar_invoice_id},
        trace_id=trace_id,
    )


def emit_eway_bill_created(
    org_id: str,
    *,
    eway_bill_id: str,
    eway_bill_no: str,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="eway.bill.created",
        org_id=org_id,
        source="erp.tax",
        entity_type="eway_bill",
        entity_id=eway_bill_id,
        payload={"eway_bill_id": eway_bill_id, "eway_bill_no": eway_bill_no},
        trace_id=trace_id,
    )


def emit_compliance_alert(
    org_id: str,
    *,
    alert_type: str,
    summary: str,
    severity: str = "medium",
    trace_id: str | None = None,
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="compliance.alert",
        org_id=org_id,
        source="erp.tax",
        entity_type="compliance_alert",
        entity_id=alert_type,
        payload={"alert_type": alert_type, "summary": summary, "severity": severity},
        trace_id=trace_id,
    )
