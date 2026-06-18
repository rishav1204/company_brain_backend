from __future__ import annotations

from app.modules.platform.notifications.services.realtime_service import realtime_notification_service


class ArRealtimeService:
    def push_invoice_issued(self, org_id: str, *, invoice_id: str, amount: float) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="ar.invoice.issued",
            priority="medium",
            title="Sales invoice issued",
            body=f"Invoice {invoice_id} issued for {amount:,.2f} — receivable created.",
            metadata={"invoice_id": invoice_id, "amount": amount},
        )

    def push_collection_reminder(self, org_id: str, *, invoice_id: str, stage: str) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="ar.collection.reminder",
            priority="high" if "overdue" in stage else "medium",
            title="Collection reminder",
            body=f"Invoice {invoice_id}: {stage.replace('_', ' ')}",
            metadata={"invoice_id": invoice_id, "stage": stage},
        )

    def push_payment_received(self, org_id: str, *, receipt_id: str, amount: float) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="ar.payment.received",
            priority="high",
            title="Payment received",
            body=f"Receipt {receipt_id} recorded ({amount:,.2f}).",
            metadata={"receipt_id": receipt_id, "amount": amount},
        )


ar_realtime_service = ArRealtimeService()
