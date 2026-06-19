from __future__ import annotations

from app.modules.platform.events.services.event_service import platform_event_service


def emit_pr_created(org_id: str, *, pr_id: str, pr_number: str, amount: float) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="pr.created",
        source="erp.procurement",
        payload={"pr_id": pr_id, "pr_number": pr_number, "amount": amount},
    )


def emit_pr_approved(org_id: str, *, pr_id: str, pr_number: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="pr.approved",
        source="erp.procurement",
        payload={"pr_id": pr_id, "pr_number": pr_number},
    )


def emit_po_created(org_id: str, *, po_id: str, po_number: str, vendor_id: str, amount: float) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="po.created",
        source="erp.procurement",
        payload={"po_id": po_id, "po_number": po_number, "vendor_id": vendor_id, "amount": amount},
    )
    platform_event_service.publish(
        org_id=org_id,
        event_type="erp.po.created",
        source="erp.procurement",
        payload={"po_id": po_id, "po_number": po_number},
    )


def emit_po_approved(org_id: str, *, po_id: str, po_number: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="po.approved",
        source="erp.procurement",
        payload={"po_id": po_id, "po_number": po_number},
    )
    platform_event_service.publish(
        org_id=org_id,
        event_type="erp.po.approved",
        source="erp.procurement",
        payload={"po_id": po_id, "po_number": po_number},
    )


def emit_po_sent(org_id: str, *, po_id: str, po_number: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="po.sent",
        source="erp.procurement",
        payload={"po_id": po_id, "po_number": po_number},
    )


def emit_grn_created(org_id: str, *, grn_id: str, grn_number: str, po_id: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="grn.created",
        source="erp.procurement",
        payload={"grn_id": grn_id, "grn_number": grn_number, "po_id": po_id},
    )


def emit_grn_confirmed(org_id: str, *, grn_id: str, grn_number: str, po_id: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="grn.confirmed",
        source="erp.procurement",
        payload={"grn_id": grn_id, "grn_number": grn_number, "po_id": po_id},
    )


def emit_match_completed(org_id: str, *, match_id: str, match_status: str, po_id: str, ap_invoice_id: str | None) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="three_way_match.completed",
        source="erp.procurement",
        payload={
            "match_id": match_id,
            "match_status": match_status,
            "po_id": po_id,
            "ap_invoice_id": ap_invoice_id,
        },
    )


def emit_match_exception(org_id: str, *, match_id: str, po_id: str, variance: dict) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="three_way_match.exception",
        source="erp.procurement",
        payload={"match_id": match_id, "po_id": po_id, "variance": variance},
    )
