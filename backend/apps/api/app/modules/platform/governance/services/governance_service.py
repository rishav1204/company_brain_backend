from __future__ import annotations

from typing import Any

from app.modules.platform.governance.services.audit_service import audit_service
from app.modules.platform.governance.services.policy_service import governance_policy_service


class GovernanceViolation(Exception):
    def __init__(self, message: str, *, violations: list | None = None) -> None:
        super().__init__(message)
        self.violations = violations or []


class GovernanceService:
    def evaluate_action(
        self,
        org_id: str,
        *,
        action: str,
        attrs: dict,
        roles: list[str],
        created_by: str | None = None,
        actor_user_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        object_ref: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        source_service: str = "governance",
    ) -> dict[str, Any]:
        result = governance_policy_service.evaluate(
            org_id,
            action=action,
            attrs=attrs,
            roles=roles,
            created_by=created_by,
            actor_user_id=actor_user_id,
        )
        audit_service.record(
            org_id=org_id,
            actor_type="user",
            actor_id=actor_user_id or "unknown",
            action=f"governance.evaluate.{action}",
            object_ref=object_ref or f"governance:{action}",
            payload={"allowed": result.allowed, "reason": result.reason, "violations": result.violations},
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            request_id=request_id,
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
            source_service=source_service,
        )
        if not result.allowed:
            raise GovernanceViolation(result.reason or "Policy denied", violations=result.violations)
        return {"allowed": True, "violations": []}

    def enforce_maker_checker(self, *, org_id: str, created_by: str, actor_user_id: str, action: str) -> None:
        governance_policy_service.evaluate(
            org_id,
            action=action,
            attrs={},
            roles=[],
            created_by=created_by,
            actor_user_id=actor_user_id,
        )


governance_service = GovernanceService()
