from __future__ import annotations

from app.modules.platform.governance.services.compliance_service import compliance_service
from app.modules.platform.governance.services.policy_service import governance_policy_service


class RiskService:
    def assess_payment_risk(self, org_id: str, *, payment_id: str, amount: float, attrs: dict) -> dict:
        dup = governance_policy_service.check_duplicate_payment(
            org_id,
            payment_id=payment_id,
            amount=amount,
            vendor_id=str(attrs.get("vendor_id", "")),
        )
        if dup:
            return {"payment_id": payment_id, "severity": "high", "allowed": False, "reason": dup}
        result = governance_policy_service.evaluate(
            org_id,
            action="payment.approve",
            attrs={**attrs, "amount": amount},
            roles=attrs.get("roles", []),
            dry_run=True,
        )
        severity = "high" if not result.allowed else "low"
        if severity == "high":
            compliance_service.record(
                org_id,
                compliance_type="payment.risk",
                status="flagged",
                severity="warning",
                related_entity_type="payment",
                related_entity_id=payment_id,
                details={"amount": amount, "reason": result.reason},
            )
            try:
                from app.modules.platform.events.events.ai_events import emit_risk_detected

                emit_risk_detected(
                    org_id,
                    entity_type="payment",
                    entity_id=payment_id,
                    risk={"reason": result.reason, "amount": amount},
                )
            except Exception:
                pass
            try:
                from app.modules.platform.events.services.event_service import platform_event_service

                platform_event_service.publish(
                    event_type="suspicious.activity.detected",
                    org_id=org_id,
                    source="governance.risk",
                    entity_type="payment",
                    entity_id=payment_id,
                    payload={"summary": result.reason, "amount": amount, "severity": "high"},
                )
            except Exception:
                pass
        return {"payment_id": payment_id, "severity": severity, "allowed": result.allowed, "reason": result.reason}


risk_service = RiskService()
