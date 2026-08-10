from unittest.mock import MagicMock, patch

from app.modules.erp.accounts_payable.services.vendor_service import vendor_service


@patch("app.modules.erp.accounts_payable.services.vendor_service.vendor_bank_repository.create")
@patch("app.modules.erp.accounts_payable.services.vendor_service.vendor_repository.get")
@patch("app.modules.erp.accounts_payable.services.vendor_service.encrypt_field", return_value="enc")
@patch("app.modules.erp.accounts_payable.events.ap_events.emit_vendor_bank_account_changed")
def test_add_bank_account_audits_and_emits(mock_emit, _enc, mock_get_vendor, mock_create) -> None:
    mock_get_vendor.return_value = {"id": "v1"}
    mock_create.return_value = {"id": "bank-1", "ifsc_code": "HDFC0001", "is_primary": True}

    with patch.object(vendor_service, "_audit_bank_account") as mock_audit:
        row = vendor_service.add_bank_account(
            "org-1",
            vendor_id="v1",
            account_number="1234567890",
            ifsc_code="hdfc0001",
            bank_name="HDFC",
            is_primary=True,
            actor_id="user-1",
        )

    assert row["id"] == "bank-1"
    mock_audit.assert_called_once()
    call = mock_audit.call_args.kwargs
    assert call["action"] == "vendor.bank_account.added"
    assert call["payload"]["account_last4"] == "7890"
    mock_emit.assert_called_once()
    assert mock_emit.call_args.kwargs["change_type"] == "added"
