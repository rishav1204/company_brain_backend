from __future__ import annotations

from typing import Any

from app.modules.platform.governance.repositories.compliance_repository import compliance_repository
from app.modules.platform.governance.services.audit_service import audit_service


class ComplianceService:
    GST_TYPES = ("gst.filed", "gst.mismatch", "gst.itc_issue", "gst.delayed_filing")
    TDS_TYPES = ("tds.deducted", "tds.return_filed", "tds.challan")

    def record(
        self,
        org_id: str,
        *,
        compliance_type: str,
        status: str,
        severity: str = "info",
        related_entity_type: str | None = None,
        related_entity_id: str | None = None,
        details: dict | None = None,
        actor_id: str = "system",
    ) -> dict[str, Any]:
        row = compliance_repository.record(
            org_id,
            compliance_type=compliance_type,
            status=status,
            severity=severity,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            details=details,
        )
        audit_service.record(
            org_id=org_id,
            actor_type="system",
            actor_id=actor_id,
            action=f"compliance.{compliance_type}",
            object_ref=f"compliance:{row.get('id', '')}",
            payload=details or {},
            entity_type=related_entity_type,
            entity_id=related_entity_id,
            source_service="governance.compliance",
        )
        from app.services.metrics import metrics_store

        metrics_store.incr_governance_compliance_alert()
        try:
            from app.modules.platform.governance.events.compliance_events import emit_compliance_alert

            emit_compliance_alert(org_id, compliance_type=compliance_type, status=status, event_id=row.get("id", ""))
        except Exception:
            pass
        return row

    def list_events(self, org_id: str, **filters: Any) -> list[dict]:
        return compliance_repository.list_events(org_id, **filters)

    def track_gst_filing(self, org_id: str, *, return_id: str, period: str, status: str) -> dict:
        severity = "info" if status == "filed" else "warning"
        return self.record(
            org_id,
            compliance_type="gst.filed",
            status=status,
            severity=severity,
            related_entity_type="gst_return",
            related_entity_id=return_id,
            details={"period": period},
        )

    def track_gst_itc_mismatch(self, org_id: str, *, return_id: str, delta_amount: float) -> dict:
        return self.record(
            org_id,
            compliance_type="gst.itc_mismatch",
            status="open",
            severity="warning",
            related_entity_type="gst_return",
            related_entity_id=return_id,
            details={"delta_amount": delta_amount},
        )

    def track_gst_delayed_filing(self, org_id: str, *, return_id: str, days_late: int) -> dict:
        row = self.record(
            org_id,
            compliance_type="gst.delayed_filing",
            status="overdue",
            severity="high" if days_late > 5 else "warning",
            related_entity_type="gst_return",
            related_entity_id=return_id,
            details={"days_late": days_late},
        )
        try:
            from app.modules.platform.governance.events.compliance_events import emit_gst_deadline_approaching

            emit_gst_deadline_approaching(
                org_id, deadline=f"{days_late} days overdue", compliance_type="gst.delayed_filing"
            )
        except Exception:
            pass
        return row

    def track_tds(self, org_id: str, *, compliance_type: str, entity_id: str, status: str, details: dict | None = None) -> dict:
        if compliance_type not in self.TDS_TYPES:
            raise ValueError(f"Unknown TDS compliance type: {compliance_type}")
        return self.record(
            org_id,
            compliance_type=compliance_type,
            status=status,
            severity="info",
            related_entity_type="tds",
            related_entity_id=entity_id,
            details=details,
        )

    def track_approval_bypass(self, org_id: str, *, entity_type: str, entity_id: str, actor_id: str, reason: str) -> dict:
        return self.record(
            org_id,
            compliance_type="approval.bypassed",
            status="flagged",
            severity="critical",
            related_entity_type=entity_type,
            related_entity_id=entity_id,
            details={"actor_id": actor_id, "reason": reason},
            actor_id=actor_id,
        )


compliance_service = ComplianceService()
