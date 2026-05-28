from __future__ import annotations

from app.services.logger import log_event


class GovernanceRealtimeBridge:
    def push_violation(self, org_id: str, envelope: dict) -> None:
        try:
            from app.modules.workflows.services.realtime_hub import workflow_realtime_hub

            workflow_realtime_hub.publish(
                org_id,
                {
                    "event_type": "policy.violation.detected",
                    "channel": "risk_alerts",
                    "payload": envelope.get("payload", {}),
                    "toast": True,
                },
            )
        except Exception:
            log_event("governance.realtime.violation", org_id=org_id)

    def push_compliance_alert(self, org_id: str, envelope: dict) -> None:
        try:
            from app.modules.workflows.services.realtime_hub import workflow_realtime_hub

            workflow_realtime_hub.publish(
                org_id,
                {
                    "event_type": "compliance.alert.generated",
                    "channel": "compliance_alerts",
                    "payload": envelope.get("payload", {}),
                    "toast": True,
                },
            )
        except Exception:
            log_event("governance.realtime.compliance", org_id=org_id)


governance_realtime_bridge = GovernanceRealtimeBridge()
