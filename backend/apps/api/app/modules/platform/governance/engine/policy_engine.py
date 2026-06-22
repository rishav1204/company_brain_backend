from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.platform.governance.engine import rule_engine, sod_engine, risk_engine, approval_engine
from app.modules.platform.governance.repositories.policy_decision_repository import policy_decision_repository
from app.modules.platform.governance.events import policy_events


@dataclass
class PolicyEvaluationResult:
    allowed: bool
    reason: str | None = None
    violations: list[dict] = field(default_factory=list)
    decision: str = "allowed"
    risk_level: str = "LOW"
    approval_chain: list[dict] = field(default_factory=list)
    policy_code: str | None = None
    decision_id: str | None = None

    def to_legacy_payment_policy_dict(self, *, amount: float, payment_type: str) -> dict:
        return approval_engine.to_legacy_payment_policy(amount, payment_type, self.approval_chain)


def evaluate(
    org_id: str,
    *,
    action: str,
    attrs: dict | None = None,
    roles: list[str] | None = None,
    actor_user_id: str | None = None,
    created_by: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    human_approved: bool = False,
    actor_type: str | None = None,
    dry_run: bool = False,
) -> PolicyEvaluationResult:
    attrs = dict(attrs or {})
    roles = list(roles or [])
    violations: list[dict] = []

    agent_block = sod_engine.check_agent_restrictions(actor_type=actor_type, action=action)
    if agent_block:
        return _finalize(
            org_id,
            action=action,
            result=PolicyEvaluationResult(
                allowed=False,
                reason=agent_block,
                violations=[{"type": "agent_restriction", "message": agent_block, "severity": "critical"}],
                decision="denied",
            ),
            attrs=attrs,
            object_type=object_type,
            object_id=object_id,
            actor_user_id=actor_user_id,
            dry_run=dry_run,
        )

    sod_msg = sod_engine.check_sod(action=action, created_by=created_by, actor_user_id=actor_user_id, org_id=org_id)
    if sod_msg:
        violations.append({"type": "maker_checker", "message": sod_msg, "severity": "critical"})
        return _finalize(
            org_id,
            action=action,
            result=PolicyEvaluationResult(allowed=False, reason=sod_msg, violations=violations, decision="denied"),
            attrs=attrs,
            object_type=object_type,
            object_id=object_id,
            actor_user_id=actor_user_id,
            dry_run=dry_run,
        )

    rule_violations = rule_engine.evaluate_rules(org_id, action=action, attrs=attrs, roles=roles)
    if rule_violations:
        return _finalize(
            org_id,
            action=action,
            result=PolicyEvaluationResult(
                allowed=False,
                reason=rule_violations[0].get("message"),
                violations=rule_violations,
                decision="denied",
                policy_code=rule_violations[0].get("type"),
            ),
            attrs=attrs,
            object_type=object_type,
            object_id=object_id,
            actor_user_id=actor_user_id,
            dry_run=dry_run,
        )

    risk_level = risk_engine.assess_risk(action=action, attrs=attrs)
    amount = float(attrs.get("amount", 0) or 0)
    chain = approval_engine.resolve_chain(
        org_id,
        action=action,
        amount=amount,
        department=attrs.get("department"),
        company_id=attrs.get("company_id"),
    )
    missing = approval_engine.required_roles_missing(chain, roles)

    if missing and not human_approved:
        return _finalize(
            org_id,
            action=action,
            result=PolicyEvaluationResult(
                allowed=False,
                reason=f"Approval required: {', '.join(missing)}",
                violations=[{"type": "approval_matrix", "message": f"Missing roles: {missing}", "severity": "medium"}],
                decision="approval_required",
                risk_level=risk_level,
                approval_chain=chain,
                policy_code="APPROVAL_MATRIX",
            ),
            attrs=attrs,
            object_type=object_type,
            object_id=object_id,
            actor_user_id=actor_user_id,
            dry_run=dry_run,
        )

    if risk_engine.risk_blocks_execution(risk_level, human_approved=human_approved) and attrs.get("fiscal_period_open") is False:
        return _finalize(
            org_id,
            action=action,
            result=PolicyEvaluationResult(
                allowed=False,
                reason="Critical risk: fiscal period closed",
                decision="override_required",
                risk_level=risk_level,
                approval_chain=chain,
                policy_code="FISCAL_PERIOD_LOCK",
            ),
            attrs=attrs,
            object_type=object_type,
            object_id=object_id,
            actor_user_id=actor_user_id,
            dry_run=dry_run,
        )

    return _finalize(
        org_id,
        action=action,
        result=PolicyEvaluationResult(
            allowed=True,
            reason="policy_allow",
            decision="allowed",
            risk_level=risk_level,
            approval_chain=chain,
        ),
        attrs=attrs,
        object_type=object_type,
        object_id=object_id,
        actor_user_id=actor_user_id,
        dry_run=dry_run,
    )


def _finalize(
    org_id: str,
    *,
    action: str,
    result: PolicyEvaluationResult,
    attrs: dict,
    object_type: str | None,
    object_id: str | None,
    actor_user_id: str | None,
    dry_run: bool,
) -> PolicyEvaluationResult:
    if dry_run:
        return result
    row = policy_decision_repository.record(
        org_id,
        action=action,
        decision=result.decision,
        object_type=object_type,
        object_id=object_id,
        policy_code=result.policy_code,
        risk_level=result.risk_level,
        approval_chain=result.approval_chain,
        input_context=attrs,
        reason=result.reason,
        actor_id=actor_user_id,
    )
    result.decision_id = row.get("id")
    if result.allowed:
        policy_events.emit_policy_approved(org_id, action=action, decision_id=result.decision_id or "")
    elif result.decision == "override_required":
        policy_events.emit_override_required(org_id, action=action, reason=result.reason or "")
    else:
        policy_events.emit_policy_denied(org_id, action=action, reason=result.reason or "")
    if result.risk_level in {"HIGH", "CRITICAL"}:
        policy_events.emit_risk_detected(org_id, action=action, risk_level=result.risk_level)
    policy_events.emit_policy_evaluated(org_id, action=action, decision=result.decision, decision_id=result.decision_id)
    return result
