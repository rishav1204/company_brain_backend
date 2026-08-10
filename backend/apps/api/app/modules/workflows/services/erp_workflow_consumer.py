from __future__ import annotations

from typing import Any

from app.modules.workflows.services.workflow_service import workflow_service

_ENTITY_WORKFLOW_MAP = {
    "invoice": "AP_INVOICE_APPROVAL",
    "payment": "PAYMENT_APPROVAL",
    "journal": "JOURNAL_APPROVAL",
    "gst_return": "GST_FILING",
    "tds_return": "TDS_FILING",
    "e_invoice": "EINVOICE_GENERATION",
    "reconciliation": "BANK_RECONCILIATION",
    "vendor": "VENDOR_ONBOARDING",
    "sales_invoice": "AR_INVOICE_APPROVAL",
    "customer_credit": "AR_CREDIT_LIMIT_APPROVAL",
    "ar_writeoff": "AR_WRITE_OFF_APPROVAL",
    "treasury_payment": "TREASURY_PAYMENT_APPROVAL",
    "fiscal_period": "PERIOD_CLOSE",
    "period_reopen": "PERIOD_REOPEN",
    "purchase_requisition": "PR_APPROVAL",
    "purchase_order": "PO_APPROVAL",
    "goods_receipt": "GRN_CONFIRMATION",
    "procurement_exception": "PROCUREMENT_EXCEPTION",
    "expense_claim": "EXPENSE_CLAIM_APPROVAL",
    "expense_policy_exception": "EXPENSE_POLICY_EXCEPTION",
    "expense_reimbursement": "EXPENSE_REIMBURSEMENT",
    "asset_capitalization": "ASSET_CAPITALIZATION_APPROVAL",
    "asset_disposal": "ASSET_DISPOSAL_APPROVAL",
    "asset_impairment": "ASSET_IMPAIRMENT_APPROVAL",
    "inventory_adjustment": "INVENTORY_ADJUSTMENT_APPROVAL",
    "voucher": "VOUCHER_APPROVAL",
    "ap_credit_note": "AP_CREDIT_NOTE_APPROVAL",
    "ap_debit_note": "AP_DEBIT_NOTE_APPROVAL",
    "ar_credit_note": "AR_CREDIT_NOTE_APPROVAL",
}

_ENTITY_POLICY_ACTION = {
    # Wave 2: provide a deterministic policy action for workflow execution gating.
    "invoice": "invoice.approve",
    "payment": "payment.execute",
    "treasury_payment": "treasury.payment.execute",
    "gst_return": "gst.return.file",
    "tds_return": "tds.return.file",
    "e_invoice": "einvoice.generate",
    "reconciliation": "bank.reconciliation.approve",
    "fiscal_period": "fiscal.close",
    "period_reopen": "fiscal.reopen",
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
    metadata.setdefault("policy_action", _ENTITY_POLICY_ACTION.get(entity_type))
    return workflow_service.start_workflow(
        org_id=org_id,
        user_id=str(payload.get("started_by") or payload.get("user_id") or ""),
        workflow_key=workflow_key,
        entity_type=entity_type,
        entity_id=entity_id or None,
        metadata=metadata,
        trace_id=trace_id,
    )
