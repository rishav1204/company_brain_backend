from __future__ import annotations

from app.modules.erp.procurement.workflows.pr_approval_workflow import workflow_metadata_for_amount


def po_workflow_metadata(amount: float, *, vendor_id: str, po_id: str, thresholds: list[dict] | None = None) -> dict:
    meta = workflow_metadata_for_amount(amount, thresholds=thresholds)
    meta.update({"vendor_id": vendor_id, "po_id": po_id})
    return meta
