from __future__ import annotations

from app.modules.erp.compliance.services.obligation_service import obligation_service
from app.modules.erp.tax.events.tax_events import emit_compliance_alert


class TaxTreasuryBridgeService:
    def handle_tax_payment_executed(self, org_id: str, *, payment_request_id: str, amount: float, metadata: dict | None = None) -> dict:
        meta = metadata or {}
        return_period = str(meta.get("return_period") or "")[:7] or None
        obligation_type = str(meta.get("tax_obligation") or "TAX_PAYMENT")
        result = obligation_service.complete_by_source(
            org_id,
            compliance_code=obligation_type,
            return_period=return_period,
            source_id=payment_request_id,
        )
        emit_compliance_alert(
            org_id,
            alert_type="tax.payment.recorded",
            summary=f"Tax payment of ₹{amount:,.2f} recorded against {obligation_type}",
            severity="low",
        )
        return {
            "payment_request_id": payment_request_id,
            "calendar_items_completed": result.get("completed_count", 0),
            "return_period": return_period,
        }


tax_treasury_bridge_service = TaxTreasuryBridgeService()
