from __future__ import annotations

from app.modules.platform.notifications.services.realtime_service import realtime_notification_service


class TreasuryRealtimeService:
    def push_payment_executed(self, org_id: str, *, payment_request_id: str, amount: float) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="treasury.payment.executed",
            priority="high",
            title="Payment executed",
            body=f"Treasury payment {payment_request_id} executed ({amount:,.2f}).",
            metadata={"payment_request_id": payment_request_id, "amount": amount},
        )

    def push_reconciliation_pending(self, org_id: str, *, reconciliation_id: str) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="erp.reconciliation.pending",
            priority="medium",
            title="Reconciliation needs review",
            body=f"Reconciliation {reconciliation_id} requires attention.",
            metadata={"reconciliation_id": reconciliation_id},
        )

    def push_cash_position_updated(self, org_id: str, *, position: dict) -> None:
        net = position.get("net_liquidity") or position.get("available_cash") or 0
        realtime_notification_service.push_toast(
            org_id,
            notification_type="cash.position.updated",
            priority="low",
            title="Cash position updated",
            body=f"Net liquidity: {float(net):,.2f}.",
            metadata={"position": position},
        )


treasury_realtime_service = TreasuryRealtimeService()
