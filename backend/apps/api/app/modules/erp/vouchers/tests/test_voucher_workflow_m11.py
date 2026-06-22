from app.modules.erp.vouchers.services.voucher_validation_service import voucher_validation_service
from app.modules.workflows.services.erp_workflow_consumer import _ENTITY_WORKFLOW_MAP
from app.services.event_consumers import _handle_voucher_workflow_approval


def test_voucher_validation_requires_lines() -> None:
    try:
        voucher_validation_service.validate(
            "org",
            voucher={"voucher_type": "journal", "voucher_date": "2026-06-01"},
            lines=[],
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "line" in str(exc).lower()


def test_voucher_workflow_map_entries() -> None:
    assert _ENTITY_WORKFLOW_MAP["voucher"] == "VOUCHER_APPROVAL"
    assert _ENTITY_WORKFLOW_MAP["ap_credit_note"] == "AP_CREDIT_NOTE_APPROVAL"
    assert _ENTITY_WORKFLOW_MAP["ar_credit_note"] == "AR_CREDIT_NOTE_APPROVAL"


def test_voucher_workflow_handler_unknown_entity() -> None:
    assert _handle_voucher_workflow_approval("org", {"entity_type": "invoice"}) is False
