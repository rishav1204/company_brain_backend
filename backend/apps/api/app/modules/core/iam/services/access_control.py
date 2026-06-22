"""Unified IAM + legacy policy gate for Finance OS routes."""

from __future__ import annotations

from app.modules.core.iam.events.role_events import emit_permission_denied
from app.modules.core.iam.services.auth_service import iam_db_enabled
from app.modules.core.iam.services.branch_scope_service import evaluate_branch_scope
from app.modules.core.iam.services.fiscal_period_service import is_fiscal_period_open
from app.modules.core.iam.services.identity_resolver import resolve_user_id
from app.modules.core.iam.services.maker_checker_service import (
    MakerCheckerViolation,
    enforce_maker_checker,
    requires_maker_checker,
)
from app.modules.core.iam.services.policy_evaluator import evaluate_iam_permission
from app.modules.core.iam.services.policy_rules_service import evaluate_policy_context_rules
from app.modules.core.iam.services.rbac_service import merge_policy_context, permission_key_for_action
from app.services.metrics import metrics_store
from app.services.object_context import ObjectContext
from app.services.policy_service import PolicyDecision, evaluate_object_permission
from app.services.trace import trace_span


def evaluate_access(
    *,
    org_id: str,
    user_id: str,
    roles: list[str],
    action: str,
    object_context: ObjectContext,
    attrs: dict | None = None,
    created_by: str | None = None,
    human_approved: bool = False,
    object_branch_id: str | None = None,
    object_company_id: str | None = None,
    emit_denial_event: bool = True,
) -> PolicyDecision:
    with trace_span("iam.evaluate_access", org_id=org_id, action=action, object_type=object_context.object_type):
        return _evaluate_access_inner(
            org_id=org_id,
            user_id=user_id,
            roles=roles,
            action=action,
            object_context=object_context,
            attrs=attrs,
            created_by=created_by,
            human_approved=human_approved,
            object_branch_id=object_branch_id,
            object_company_id=object_company_id,
            emit_denial_event=emit_denial_event,
        )


def _evaluate_access_inner(
    *,
    org_id: str,
    user_id: str,
    roles: list[str],
    action: str,
    object_context: ObjectContext,
    attrs: dict | None = None,
    created_by: str | None = None,
    human_approved: bool = False,
    object_branch_id: str | None = None,
    object_company_id: str | None = None,
    emit_denial_event: bool = True,
) -> PolicyDecision:
    attrs = attrs or merge_policy_context(org_id, user_id) if iam_db_enabled() else (attrs or {})

    fiscal_open = is_fiscal_period_open(org_id, object_context.company_id)
    gov_attrs = dict(attrs)
    gov_attrs.setdefault("fiscal_period_open", fiscal_open)

    from app.modules.platform.governance.engine.policy_engine import evaluate as policy_engine_evaluate

    gov_result = policy_engine_evaluate(
        org_id,
        action=action,
        attrs={
            **gov_attrs,
            "amount": object_context.amount,
            "vendor_risk": object_context.vendor_risk,
            "fiscal_period_open": fiscal_open,
        },
        roles=roles,
        actor_user_id=user_id,
        created_by=created_by or object_context.owner_user_id,
        object_type=object_context.object_type,
        object_id=object_context.object_id or None,
        human_approved=human_approved,
        actor_type=attrs.get("actor_type"),
        dry_run=False,
    )
    if not gov_result.allowed:
        return _deny(org_id, user_id, action, gov_result.reason or "policy_denied", ["policy_engine_denied"], emit_denial_event)

    if attrs.get("read_only") and action not in {"read", "list", "get"} and not action.endswith(".read"):
        return _deny(org_id, user_id, action, "read_only_role", ["read_only_denied"], emit_denial_event)

    branch_decision = evaluate_branch_scope(
        attrs=attrs,
        object_branch_id=object_branch_id or object_context.branch_id,
        object_company_id=object_company_id or object_context.company_id,
    )
    if branch_decision is not None:
        return _deny(org_id, user_id, action, branch_decision.reason, branch_decision.checks or [], emit_denial_event)

    resource = object_context.object_type or "action"
    rule_decision = evaluate_policy_context_rules(
        policy_context=attrs,
        resource=resource,
        action=action,
        amount=object_context.amount,
        fiscal_period_open=fiscal_open,
        branch_id=object_branch_id or object_context.branch_id,
        allowed_branch_ids=attrs.get("allowed_branch_ids") if isinstance(attrs.get("allowed_branch_ids"), list) else None,
    )
    if rule_decision is not None:
        return _deny(org_id, user_id, action, rule_decision.reason, rule_decision.checks or [], emit_denial_event)

    if action in {"post_journal", "journal.post"} and not fiscal_open:
        return _deny(org_id, user_id, action, "fiscal_period_closed", ["fiscal_period_denied"], emit_denial_event)

    creator = created_by or object_context.owner_user_id
    if requires_maker_checker(action) and creator:
        try:
            enforce_maker_checker(
                created_by=resolve_user_id(org_id, creator) or creator,
                actor_user_id=resolve_user_id(org_id, user_id) or user_id,
                org_id=org_id,
            )
        except MakerCheckerViolation as exc:
            return _deny(org_id, user_id, action, str(exc), ["maker_checker_denied"], emit_denial_event)

    if iam_db_enabled():
        permission_key = permission_key_for_action(action, resource)
        decision = evaluate_iam_permission(
            org_id=org_id,
            user_id=user_id,
            roles=roles,
            permission_key=permission_key,
            action=action,
            object_context=object_context,
            attrs=attrs,
            actor_user_id=user_id,
            created_by=None,
            human_approved=human_approved,
        )
    else:
        decision = evaluate_object_permission(
            roles=roles,
            action=action,
            object_context=object_context,
            attrs=attrs,
            actor_user_id=user_id,
            human_approved=human_approved,
        )

    if not decision.allowed and emit_denial_event:
        _emit_denial(org_id, user_id, action, decision)
    return decision


def _deny(
    org_id: str,
    user_id: str,
    action: str,
    reason: str,
    checks: list[str],
    emit_denial_event: bool,
) -> PolicyDecision:
    decision = PolicyDecision(allowed=False, reason=reason, checks=checks)
    if emit_denial_event:
        _emit_denial(org_id, user_id, action, decision)
    return decision


def _emit_denial(org_id: str, user_id: str, action: str, decision: PolicyDecision) -> None:
    metrics_store.incr_iam_permission_denied()
    try:
        emit_permission_denied(org_id=org_id, user_id=user_id, action=action, reason=decision.reason)
    except Exception:
        pass
