from __future__ import annotations

from app.modules.platform.events.services.event_service import platform_event_service


def emit_claim_created(org_id: str, *, claim_id: str, claim_number: str, amount: float) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="expense.claim.created",
        source="erp.expense",
        payload={"claim_id": claim_id, "claim_number": claim_number, "amount": amount},
    )


def emit_claim_approved(org_id: str, *, claim_id: str, claim_number: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="expense.claim.approved",
        source="erp.expense",
        payload={"claim_id": claim_id, "claim_number": claim_number},
    )


def emit_claim_rejected(org_id: str, *, claim_id: str, reason: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="expense.claim.rejected",
        source="erp.expense",
        payload={"claim_id": claim_id, "reason": reason},
    )


def emit_reimbursement_scheduled(org_id: str, *, claim_id: str, payment_request_id: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="expense.reimbursement.scheduled",
        source="erp.expense",
        payload={"claim_id": claim_id, "payment_request_id": payment_request_id},
    )


def emit_reimbursed(org_id: str, *, claim_id: str, payment_request_id: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="expense.reimbursed",
        source="erp.expense",
        payload={"claim_id": claim_id, "payment_request_id": payment_request_id},
    )


def emit_policy_violation(org_id: str, *, claim_id: str, violation_type: str, message: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="policy.violation.detected",
        source="erp.expense",
        payload={"claim_id": claim_id, "violation_type": violation_type, "message": message},
    )


def emit_receipt_extracted(org_id: str, *, document_id: str, claim_id: str | None = None) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="expense.receipt.extracted",
        source="erp.expense",
        payload={"document_id": document_id, "claim_id": claim_id},
    )
