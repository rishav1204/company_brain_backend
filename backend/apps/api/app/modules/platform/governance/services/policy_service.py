from __future__ import annotations

from typing import Any

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
        row = policy_repository.upsert(
            org_id,
            policy_key=policy_key,
            policy_type=policy_type,
            conditions=conditions,
            actions=actions,
            is_active=is_active,
            priority=priority,
        )
        from app.modules.platform.governance.engine import policy_cache_engine

        policy_cache_engine.invalidate_org(org_id)
        return row

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
        object_type: str | None = None,
        object_id: str | None = None,
        human_approved: bool = False,
        actor_type: str | None = None,
    ) -> PolicyEvaluationResult:
        from app.modules.platform.governance.engine.policy_engine import evaluate as engine_evaluate

        result = engine_evaluate(
            org_id,
            action=action,
            attrs=attrs,
            roles=roles,
            created_by=created_by,
            actor_user_id=actor_user_id,
            object_type=object_type,
            object_id=object_id,
            human_approved=human_approved,
            actor_type=actor_type,
            dry_run=dry_run,
        )
        if not result.allowed and not dry_run:
            for v in result.violations:
                self._record_violation(org_id, v, action, created_by, actor_user_id)
        return PolicyEvaluationResult(
            allowed=result.allowed,
            reason=result.reason,
            violations=result.violations,
        )

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
