from unittest.mock import patch

from app.modules.platform.governance.services.forensics_service import forensics_service


def test_rollback_analysis_empty() -> None:
    with patch.object(
        forensics_service,
        "entity_timeline",
        return_value=[],
        create=True,
    ):
        with patch(
            "app.modules.platform.governance.services.forensics_service.audit_service.entity_timeline",
            return_value=[],
        ):
            result = forensics_service.rollback_analysis("org-1", entity_type="invoice", entity_id="inv-1")
    assert result["entity_type"] == "invoice"
    assert "state_chain" in result
