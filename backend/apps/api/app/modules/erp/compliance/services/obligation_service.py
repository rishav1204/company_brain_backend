from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.compliance.engine.compliance_engine import calendar_color, priority_for_status, refresh_status
from app.modules.erp.compliance.engine.due_date_engine import compute_due_date
from app.modules.erp.compliance.engine.scheduler_engine import generation_periods
from app.modules.erp.compliance.events.compliance_events import (
    emit_compliance_completed,
    emit_compliance_obligation_created,
)
from app.modules.erp.compliance.repositories.compliance_repository import (
    LEGACY_TYPE_MAP,
    compliance_obligation_repository,
    compliance_rule_repository,
    compliance_type_repository,
)


class ObligationService:
    def ensure_rules(self, org_id: str) -> int:
        rules = compliance_rule_repository.list(org_id)
        if rules:
            return 0
        return compliance_rule_repository.seed_defaults_for_org(org_id)

    def generate_for_periods(self, org_id: str, *, periods: list[str] | None = None) -> dict:
        self.ensure_rules(org_id)
        periods = periods or generation_periods()
        rules = compliance_rule_repository.list(org_id)
        created = 0
        for rule in rules:
            for period in periods:
                due = compute_due_date(
                    return_period=period,
                    frequency=str(rule.get("frequency") or "monthly"),
                    due_day=int(rule.get("due_day") or 1),
                    month_offset=int(rule.get("month_offset") or 1),
                )
                item = compliance_obligation_repository.create(
                    org_id,
                    compliance_type_id=rule["compliance_type_id"],
                    title=str(rule.get("compliance_name") or rule.get("compliance_code")),
                    due_date=due.isoformat(),
                    return_period=period,
                    status="upcoming",
                    priority="medium",
                    metadata={"regulator": rule.get("regulator"), "source_module": (rule.get("metadata") or {}).get("source_module")},
                )
                created += 1
                try:
                    emit_compliance_obligation_created(org_id, obligation_id=item["id"], compliance_code=str(rule.get("compliance_code")))
                except Exception:
                    pass
                from app.modules.erp.compliance.services.reminder_service import reminder_service

                reminder_service.schedule_for_obligation(org_id, obligation_id=item["id"], rule=rule, due_date=due)
        return {"generated": created, "periods": periods}

    def list(
        self,
        org_id: str,
        *,
        status: str | None = None,
        priority: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        assigned_to: str | None = None,
    ) -> list[dict]:
        return compliance_obligation_repository.list(
            org_id,
            status=status,
            priority=priority,
            from_date=from_date,
            to_date=to_date,
            assigned_to=assigned_to,
        )

    def create_custom(self, org_id: str, *, compliance_code: str, title: str, due_date: str, return_period: str | None = None, assigned_to: str | None = None, metadata: dict | None = None) -> dict:
        ctype = compliance_type_repository.get_by_code(compliance_code)
        if not ctype:
            raise ValueError(f"Unknown compliance type: {compliance_code}")
        item = compliance_obligation_repository.create(
            org_id,
            compliance_type_id=ctype["id"],
            title=title,
            due_date=due_date,
            return_period=return_period,
            assigned_to=assigned_to,
            metadata=metadata or {},
        )
        emit_compliance_obligation_created(org_id, obligation_id=item["id"], compliance_code=compliance_code)
        return item

    def update(self, org_id: str, obligation_id: str, *, actor_id: str | None = None, **fields) -> dict:
        old = compliance_obligation_repository.get(org_id, obligation_id)
        if not old:
            raise ValueError("Obligation not found")
        if "due_date" in fields and fields["due_date"] != old.get("due_date"):
            self._audit(org_id, action="compliance.due_date.changed", obligation_id=obligation_id, actor_id=actor_id, payload={
                "old_due_date": old.get("due_date"),
                "new_due_date": fields["due_date"],
                "reason": fields.pop("reason", None),
            })
        return compliance_obligation_repository.update(org_id, obligation_id, **fields)

    def complete(self, org_id: str, obligation_id: str, *, actor_id: str | None = None) -> dict:
        row = compliance_obligation_repository.complete(org_id, obligation_id)
        code = str(row.get("compliance_code") or "")
        if not code:
            ctype = compliance_type_repository.get_by_id(row.get("compliance_type_id", ""))
            code = (ctype or {}).get("compliance_code", "")
        emit_compliance_completed(org_id, obligation_id=obligation_id, compliance_code=code, return_period=row.get("return_period"))
        self._audit(org_id, action="compliance.completed", obligation_id=obligation_id, actor_id=actor_id, payload={"return_period": row.get("return_period")})
        return row

    def complete_by_source(self, org_id: str, *, compliance_code: str, return_period: str | None = None, source_id: str | None = None) -> dict:
        """Complete obligation when GST/TDS filing or payment events arrive."""
        compliance_code = LEGACY_TYPE_MAP.get(compliance_code, compliance_code)
        count = compliance_obligation_repository.complete_by_type_period(org_id, compliance_code=compliance_code, return_period=return_period)
        if count == 0 and return_period:
            self.generate_for_periods(org_id, periods=[return_period[:7]])
            count = compliance_obligation_repository.complete_by_type_period(org_id, compliance_code=compliance_code, return_period=return_period)
        if count > 0:
            emit_compliance_completed(org_id, obligation_id="batch", compliance_code=compliance_code, return_period=return_period)
        return {"completed_count": count, "compliance_code": compliance_code, "return_period": return_period, "source_id": source_id}

    def waive(self, org_id: str, obligation_id: str, *, reason: str, actor_id: str | None = None) -> dict:
        row = compliance_obligation_repository.waive(org_id, obligation_id, reason=reason)
        self._audit(org_id, action="compliance.waived", obligation_id=obligation_id, actor_id=actor_id, payload={"reason": reason})
        return row

    def refresh_statuses(self, org_id: str) -> int:
        obligations = compliance_obligation_repository.list(org_id)
        updates: list[tuple[str, str]] = []
        today = date.today()
        for ob in obligations:
            due = date.fromisoformat(str(ob["due_date"])[:10])
            new_status = refresh_status(due_date=due, status=str(ob.get("status") or "upcoming"), today=today)
            if new_status != ob.get("status"):
                updates.append((ob["id"], new_status))
                ob["priority"] = priority_for_status(new_status)
        return compliance_obligation_repository.refresh_all_statuses(org_id, status_updates=updates)

    def upcoming(self, org_id: str, *, within_days: int = 7) -> list[dict]:
        today = date.today()
        cutoff = today + timedelta(days=within_days)
        items = self.list(org_id, from_date=today.isoformat(), to_date=cutoff.isoformat())
        return [i for i in items if str(i.get("status")) in {"upcoming", "due_soon", "pending"}]

    def _audit(self, org_id: str, *, action: str, obligation_id: str, actor_id: str | None, payload: dict) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id,
                action=action,
                actor_id=actor_id or "system",
                object_type="compliance_obligation",
                object_id=obligation_id,
                metadata=payload,
            )
        except Exception:
            pass


obligation_service = ObligationService()
