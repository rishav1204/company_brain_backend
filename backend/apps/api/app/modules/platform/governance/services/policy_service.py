from __future__ import annotations

from typing import Any

from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker, requires_maker_checker
from app.modules.platform.governance.repositories.policy_repository import policy_repository
from app.modules.platform.governance.repositories.violation_repository import violation_repository
from app.modules.platform.governance.validators.policy_validator import validate_policy_rule
from app.services.logger import log_event


class PolicyEvaluationResult:
    def __init__(self, *, allowed: bool, reason: str | None = None, violations: list[dict] | None = None) -> None:
        self.allowed = allowed
        self.reason = reason
        self.violations = violations or []


class GovernancePolicyService:
    def schema_ready(self) -> bool:
        return policy_repository.schema_ready()

    def list_policies(self, org_id: str, *, policy_type: str | None = None) -> list[dict]:
        return policy_repository.list_active(org_id, policy_type=policy_type)

    def upsert_policy(
        self,
        org_id: str,
        *,
        policy_key: str,
        policy_type: str,
        conditions: dict,
        actions: dict,
        is_active: bool = True,
        priority: int = 100,
    ) -> dict:
        validate_policy_rule(policy_key, policy_type, conditions, actions)
        return policy_repository.upsert(
            org_id,
            policy_key=policy_key,
            policy_type=policy_type,
            conditions=conditions,
            actions=actions,
            is_active=is_active,
            priority=priority,
        )

    def simulate(
        self,
        org_id: str,
        *,
        action: str,
        attrs: dict,
        roles: list[str],
        created_by: str | None = None,
        actor_user_id: str | None = None,
    ) -> PolicyEvaluationResult:
        return self.evaluate(
            org_id,
            action=action,
            attrs=attrs,
            roles=roles,
            created_by=created_by,
            actor_user_id=actor_user_id,
            dry_run=True,
        )

    def evaluate(
        self,
        org_id: str,
        *,
        action: str,
        attrs: dict,
        roles: list[str],
        created_by: str | None = None,
        actor_user_id: str | None = None,
        dry_run: bool = False,
    ) -> PolicyEvaluationResult:
        violations: list[dict] = []

        if requires_maker_checker(action):
            try:
                enforce_maker_checker(created_by=created_by, actor_user_id=actor_user_id, org_id=org_id)
            except MakerCheckerViolation as exc:
                violation = {
                    "type": "maker_checker",
                    "message": str(exc),
                    "severity": "critical",
                }
                violations.append(violation)
                if not dry_run:
                    self._record_violation(org_id, violation, action, created_by, actor_user_id)
                return PolicyEvaluationResult(allowed=False, reason=str(exc), violations=violations)

        for rule in policy_repository.list_active(org_id):
            if not self._rule_applies(rule, action, attrs):
                continue
            blocked = self._evaluate_rule(rule, attrs, roles)
            if blocked:
                violation = {
                    "type": rule.get("policy_key", "policy"),
                    "policy_type": rule.get("policy_type"),
                    "message": blocked,
                    "severity": "high",
                }
                violations.append(violation)
                if not dry_run:
                    self._record_violation(org_id, violation, action, created_by, actor_user_id)

        if violations:
            return PolicyEvaluationResult(allowed=False, reason=violations[0].get("message"), violations=violations)

        if not dry_run and actor_user_id:
            from app.modules.core.iam.services.access_control import evaluate_access
            from app.services.object_context import ObjectContext

            iam_decision = evaluate_access(
                org_id=org_id,
                user_id=actor_user_id,
                roles=roles,
                action=action,
                object_context=ObjectContext(
                    object_type="governance",
                    object_id=org_id,
                    amount=float(attrs.get("amount", 0) or 0),
                ),
                attrs=attrs,
                created_by=created_by,
            )
            if not iam_decision.allowed:
                return PolicyEvaluationResult(allowed=False, reason=iam_decision.reason, violations=violations)

        return PolicyEvaluationResult(allowed=True)

    def _rule_applies(self, rule: dict, action: str, attrs: dict) -> bool:
        conditions = rule.get("conditions") or {}
        if conditions.get("action") and conditions["action"] != action:
            return False
        amount = float(attrs.get("amount", 0) or 0)
        if "amount_gt" in conditions and amount <= float(conditions["amount_gt"]):
            return False
        if conditions.get("closed_period") and attrs.get("fiscal_period_open") is False:
            return True
        if conditions.get("enforce") and requires_maker_checker(action):
            return True
        if conditions.get("day_of_month_gt"):
            from datetime import datetime, timezone

            if datetime.now(timezone.utc).day <= int(conditions["day_of_month_gt"]):
                return False
            return True
        return bool(conditions)

    def _evaluate_rule(self, rule: dict, attrs: dict, roles: list[str]) -> str | None:
        actions = rule.get("actions") or {}
        if actions.get("block"):
            if rule.get("policy_type") == "fiscal" and attrs.get("fiscal_period_open") is False:
                return "Fiscal period is closed"
            if rule.get("policy_type") == "approval":
                required = actions.get("require_role")
                if required and required not in roles:
                    return f"Requires role: {required}"
        return None

    def _record_violation(
        self,
        org_id: str,
        violation: dict,
        action: str,
        created_by: str | None,
        actor_user_id: str | None,
    ) -> None:
        if not violation_repository.schema_ready():
            return
        row = violation_repository.record(
            org_id,
            violation_type=violation.get("type", "policy"),
            severity=violation.get("severity", "high"),
            detected_by="governance.policy_engine",
            details={**violation, "action": action, "created_by": created_by, "actor_id": actor_user_id},
        )
        from app.services.metrics import metrics_store

        metrics_store.incr_governance_violation()
        log_event("governance.violation.recorded", org_id=org_id, violation_type=violation.get("type"))
        try:
            from app.modules.platform.governance.events.governance_events import emit_policy_violation
            from app.modules.platform.governance.services.compliance_service import compliance_service

            emit_policy_violation(org_id, violation_id=row.get("id", ""), violation_type=violation.get("type", ""))
            compliance_service.record(
                org_id,
                compliance_type="policy.violation",
                status="detected",
                severity=violation.get("severity", "high"),
                details={**violation, "violation_id": row.get("id")},
            )
        except Exception:
            pass

    def check_duplicate_payment(self, org_id: str, *, payment_id: str, amount: float, vendor_id: str | None) -> str | None:
        """Return error message if duplicate payment suspected."""
        key = f"payment:{vendor_id or 'unknown'}:{amount}"
        try:
            from app.modules.platform.governance.repositories.audit_repository import governance_audit_repository

            recent = governance_audit_repository.list_logs(
                org_id, event_type="erp.payment.completed", limit=20
            )
            for row in recent:
                payload = row.get("payload_jsonb") or {}
                if str(payload.get("payment_id")) == payment_id:
                    continue
                if float(payload.get("amount", -1)) == amount and str(payload.get("vendor_id")) == str(vendor_id):
                    return "Duplicate payment attempt detected"
        except Exception:
            pass
        return None


governance_policy_service = GovernancePolicyService()
