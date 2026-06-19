from __future__ import annotations

from datetime import date

from app.modules.erp.compliance.engine.escalation_engine import next_escalation_level, should_escalate
from app.modules.erp.compliance.events.compliance_events import emit_compliance_escalated, emit_compliance_overdue
from app.modules.erp.compliance.repositories.compliance_repository import (
    compliance_escalation_repository,
    compliance_obligation_repository,
    compliance_rule_repository,
)


class EscalationService:
    def process_overdue(self, org_id: str, *, today: date | None = None) -> dict:
        today = today or date.today()
        obligations = compliance_obligation_repository.list(org_id, status="overdue")
        escalated = 0
        rules_by_type = {r["compliance_type_id"]: r for r in compliance_rule_repository.list(org_id)}
        for ob in obligations:
            if not should_escalate(status=str(ob.get("status")), due_date=ob.get("due_date"), today=today):
                continue
            current = compliance_escalation_repository.max_level_for_obligation(org_id, ob["id"])
            rule = rules_by_type.get(ob.get("compliance_type_id", ""), {})
            levels = rule.get("escalation_levels") or ["assignee", "manager", "finance_head", "cfo"]
            if isinstance(levels, str):
                import json

                levels = json.loads(levels)
            new_level, role = next_escalation_level(current, levels)
            if new_level <= current:
                continue
            compliance_escalation_repository.create(org_id, obligation_id=ob["id"], level=new_level, role=role)
            emit_compliance_escalated(org_id, obligation_id=ob["id"], level=new_level, role=role)
            try:
                from app.modules.erp.tax.events.tax_events import emit_compliance_alert

                emit_compliance_alert(
                    org_id,
                    alert_type="compliance.escalated",
                    summary=f"{ob.get('title')} escalated to {role} (L{new_level})",
                    severity="critical" if new_level >= 3 else "high",
                )
            except Exception:
                pass
            if new_level >= 3:
                self._spawn_workflow(org_id, obligation_id=ob["id"], level=new_level)
            escalated += 1
            try:
                emit_compliance_overdue(org_id, obligation_id=ob["id"], summary=f"{ob.get('title')} is overdue")
            except Exception:
                pass
        return {"escalated": escalated}

    def list_open(self, org_id: str) -> list[dict]:
        return compliance_escalation_repository.list_open(org_id)

    def _spawn_workflow(self, org_id: str, *, obligation_id: str, level: int) -> None:
        try:
            from app.modules.workflows.services.workflow_service import workflow_service

            workflow_service.start(
                org_id,
                workflow_key="COMPLIANCE_ESCALATION",
                entity_type="compliance_obligation",
                entity_id=obligation_id,
                metadata={"escalation_level": level},
            )
        except Exception:
            pass


escalation_service = EscalationService()
