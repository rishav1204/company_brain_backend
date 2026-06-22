from __future__ import annotations

from app.modules.platform.events.services.event_service import platform_event_service


def _publish(org_id: str, event_type: str, voucher_id: str, *, payload: dict | None = None) -> dict:
    return platform_event_service.publish(
        event_type=event_type,
        org_id=org_id,
        source="erp.vouchers",
        entity_type="voucher",
        entity_id=voucher_id,
        payload={"entity_type": "voucher", "entity_id": voucher_id, **(payload or {})},
    )


def emit_voucher_created(org_id: str, voucher_id: str, **kwargs) -> dict:
    return _publish(org_id, "erp.voucher.created", voucher_id, payload=kwargs)


def emit_voucher_validated(org_id: str, voucher_id: str, **kwargs) -> dict:
    return _publish(org_id, "erp.voucher.validated", voucher_id, payload=kwargs)


def emit_voucher_submitted(org_id: str, voucher_id: str, **kwargs) -> dict:
    return _publish(org_id, "erp.voucher.submitted", voucher_id, payload=kwargs)


def emit_voucher_approved(org_id: str, voucher_id: str, **kwargs) -> dict:
    return _publish(org_id, "erp.voucher.approved", voucher_id, payload=kwargs)


def emit_voucher_journal_generated(org_id: str, voucher_id: str, *, journal_id: str) -> dict:
    return _publish(org_id, "erp.voucher.journal_generated", voucher_id, payload={"journal_id": journal_id})


def emit_voucher_posted(org_id: str, voucher_id: str, *, journal_id: str) -> dict:
    return _publish(org_id, "erp.voucher.posted", voucher_id, payload={"journal_id": journal_id})


def emit_voucher_reversed(org_id: str, voucher_id: str, **kwargs) -> dict:
    return _publish(org_id, "erp.voucher.reversed", voucher_id, payload=kwargs)


def emit_voucher_cancelled(org_id: str, voucher_id: str, **kwargs) -> dict:
    return _publish(org_id, "erp.voucher.cancelled", voucher_id, payload=kwargs)
