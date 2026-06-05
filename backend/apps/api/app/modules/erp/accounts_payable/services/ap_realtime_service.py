from __future__ import annotations

from app.modules.platform.notifications.services.realtime_service import realtime_notification_service


class ApRealtimeService:
    def push_invoice_approved(self, org_id: str, *, invoice_id: str, approver_id: str | None) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="ap.invoice.approved",
            priority="medium",
            title="Invoice approved",
            body=f"AP invoice {invoice_id} approved — liability journal created.",
            metadata={"invoice_id": invoice_id, "approved_by": approver_id},
        )

    def push_payment_scheduled(self, org_id: str, *, payment_id: str, amount: float) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="ap.payment.scheduled",
            priority="medium",
            title="Payment scheduled",
            body=f"Payment {payment_id} scheduled for {amount:,.2f}.",
            metadata={"payment_id": payment_id, "amount": amount},
        )

    def push_payment_completed(self, org_id: str, *, payment_id: str, amount: float) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="ap.payment.completed",
            priority="high",
            title="Payment completed",
            body=f"Payment {payment_id} completed ({amount:,.2f}).",
            metadata={"payment_id": payment_id, "amount": amount},
        )

    def push_invoice_due(self, org_id: str, *, invoice_id: str, due_date: str) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="ap.invoice.due",
            priority="high",
            title="Invoice due",
            body=f"Invoice {invoice_id} is due ({due_date}).",
            metadata={"invoice_id": invoice_id, "due_date": due_date},
        )


ap_realtime_service = ApRealtimeService()
