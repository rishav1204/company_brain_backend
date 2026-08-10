from __future__ import annotations


def emit_invoice_due(org_id: str, *, invoice_id: str, due_date: str) -> None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service
        from app.modules.erp.accounts_payable.services.ap_realtime_service import ap_realtime_service

        platform_event_service.publish(
            event_type="invoice.due",
            org_id=org_id,
            source="erp.ap",
            entity_type="invoice",
            entity_id=invoice_id,
            payload={"invoice_id": invoice_id, "due_date": due_date},
        )
        ap_realtime_service.push_invoice_due(org_id, invoice_id=invoice_id, due_date=due_date)
    except Exception:
        pass


def emit_vendor_bank_account_changed(
    org_id: str,
    *,
    vendor_id: str,
    bank_account_id: str,
    change_type: str,
    actor_id: str | None = None,
    ifsc_code: str | None = None,
    bank_name: str | None = None,
    is_primary: bool = False,
    account_last4: str | None = None,
) -> None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        platform_event_service.publish(
            event_type="vendor.bank_account.changed",
            org_id=org_id,
            source="erp.ap",
            entity_type="vendor_bank_account",
            entity_id=bank_account_id,
            payload={
                "vendor_id": vendor_id,
                "bank_account_id": bank_account_id,
                "change_type": change_type,
                "actor_id": actor_id,
                "ifsc_code": ifsc_code,
                "bank_name": bank_name,
                "is_primary": is_primary,
                "account_last4": account_last4,
            },
        )
    except Exception:
        pass


def emit_payment_scheduled(
    org_id: str,
    *,
    payment_id: str,
    amount: float,
    vendor_id: str | None = None,
    bank_account_id: str | None = None,
    payment_date: str | None = None,
    vendor_bank_account_id: str | None = None,
    created_by: str | None = None,
) -> None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        platform_event_service.publish(
            event_type="payment.scheduled",
            org_id=org_id,
            source="erp.ap",
            entity_type="payment",
            entity_id=payment_id,
            payload={
                "payment_id": payment_id,
                "ap_payment_id": payment_id,
                "amount": amount,
                "vendor_id": vendor_id,
                "bank_account_id": bank_account_id,
                "payment_date": payment_date,
                "vendor_bank_account_id": vendor_bank_account_id,
                "created_by": created_by,
                "create_treasury_request": True,
            },
        )
    except Exception:
        pass
