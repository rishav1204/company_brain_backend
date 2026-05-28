from dataclasses import dataclass

from app.services.object_context import ObjectContext


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    checks: list[str] | None = None


_TERMINAL_OBJECT_STATUSES = {"paid", "closed", "cancelled", "completed"}


def evaluate_permission(roles: list[str], action: str, object_type: str) -> PolicyDecision:
    return evaluate_object_permission(
        roles=roles,
        action=action,
        object_context=ObjectContext(object_type=object_type, object_id=""),
        attrs=None,
        actor_user_id=None,
    )


def _object_context_checks(
    roles: list[str],
    action: str,
    object_context: ObjectContext,
    actor_user_id: str | None,
    checks: list[str],
    attrs: dict | None = None,
) -> PolicyDecision | None:
    role_set = {role.lower() for role in roles}
    status = str(object_context.status or "").lower()
    if status in _TERMINAL_OBJECT_STATUSES and action in {"approve_payment", "post_journal", "release_filing"}:
        checks.append("terminal_object_state_denied")
        return PolicyDecision(allowed=False, reason="object_not_actionable_in_current_state", checks=checks)

    skip_legacy_amount = isinstance(attrs, dict) and (
        attrs.get("max_approve_amount") is not None or bool(attrs.get("rules"))
    )
    if not skip_legacy_amount and object_context.amount is not None and object_context.amount > 50000:
        checks.append("amount_threshold_checked")
        elevated = {"tenant_admin", "cfo", "controller"}
        if action in {"approve_payment", "post_journal"} and not any(role in elevated for role in role_set):
            checks.append("amount_threshold_denied")
            return PolicyDecision(allowed=False, reason="amount_exceeds_role_threshold", checks=checks)

    vendor_risk = str(object_context.vendor_risk or "").lower()
    if vendor_risk == "high":
        checks.append("vendor_risk_checked")
        if action in {"approve_payment", "post_journal", "release_filing"}:
            if not any(role in {"tenant_admin", "cfo", "controller"} for role in role_set):
                checks.append("high_vendor_risk_denied")
                return PolicyDecision(allowed=False, reason="high_vendor_risk_requires_elevated_role", checks=checks)

    owner_user_id = str(object_context.owner_user_id or "").strip()
    actor_id = str(actor_user_id or "").strip()
    if owner_user_id and actor_id and owner_user_id == actor_id:
        checks.append("owner_sod_checked")
        if action in {"approve_payment", "post_journal"} and "ap_preparer" in role_set:
            checks.append("owner_sod_denied")
            return PolicyDecision(
                allowed=False,
                reason="SoD violation: preparer cannot act on owned workflow object",
                checks=checks,
            )

    if object_context.invoice_type == "payroll" and "governance_admin" not in role_set:
        checks.append("payroll_object_denied")
        return PolicyDecision(allowed=False, reason="payroll_object_requires_governance_admin", checks=checks)

    return None


def evaluate_object_permission(
    roles: list[str],
    action: str,
    object_context: ObjectContext,
    attrs: dict | None = None,
    actor_user_id: str | None = None,
    human_approved: bool = False,
) -> PolicyDecision:
    checks: list[str] = ["object_context_resolved"]
    role_set = {role.lower() for role in roles}
    checks.append("rbac_checked")

    if action == "approve_payment" and "ap_preparer" in role_set:
        checks.append("sod_failed")
        return PolicyDecision(allowed=False, reason="SoD violation: preparer cannot approve payment", checks=checks)

    admin_roles = {"tenant_admin", "cfo", "controller"}
    object_denial = _object_context_checks(
        roles=roles,
        action=action,
        object_context=object_context,
        actor_user_id=actor_user_id,
        checks=checks,
        attrs=attrs,
    )
    if object_denial is not None:
        return object_denial

    if any(role in admin_roles for role in role_set):
        checks.append("admin_role_allow")
    else:
        high_risk_actions = {"approve_payment", "post_journal", "release_filing"}
        if action in high_risk_actions:
            checks.append("high_risk_action_denied")
            return PolicyDecision(allowed=False, reason=f"{action} requires elevated role", checks=checks)

        if object_context.object_type.lower() in {"payroll", "pii"} and "governance_admin" not in role_set:
            checks.append("regulatory_domain_denied")
            return PolicyDecision(allowed=False, reason="sensitive domain denied", checks=checks)

    checks.append("abac_checked")
    if not abac_allows(attrs=attrs, action=action, object_type=object_context.object_type):
        checks.append("abac_denied")
        return PolicyDecision(allowed=False, reason="abac_denied", checks=checks)

    allowed_departments = attrs.get("allowed_departments", []) if isinstance(attrs, dict) else []
    if isinstance(allowed_departments, list) and allowed_departments:
        object_department = str((attrs or {}).get("department") or object_context.workflow_type or "").strip()
        if object_department and object_department not in allowed_departments:
            checks.append("department_scope_denied")
            return PolicyDecision(allowed=False, reason="department_scope_denied", checks=checks)

    checks.append("approval_gate_checked")
    if requires_human_approval(
        action=action,
        amount=object_context.amount,
        vendor_risk=object_context.vendor_risk,
    ) and not human_approved:
        checks.append("approval_required")
        return PolicyDecision(allowed=False, reason="human_approval_required", checks=checks)

    checks.append("object_context_allow")
    return PolicyDecision(allowed=True, reason="object_context_policy_allow", checks=checks)


def requires_human_approval(
    action: str,
    amount: float | None = None,
    vendor_risk: str | None = None,
    attrs: dict | None = None,
) -> bool:
    from app.modules.core.iam.services.approval_gate_service import requires_human_approval as iam_requires_human_approval

    return iam_requires_human_approval(action=action, amount=amount, vendor_risk=vendor_risk, attrs=attrs)


def can_approve_agent_actions(roles: list[str], approver_user_id: str) -> PolicyDecision:
    role_set = {role.lower() for role in roles}
    checks = ["approval_rbac_checked", "approval_sod_checked"]
    if "ap_preparer" in role_set and ("controller" not in role_set and "cfo" not in role_set):
        return PolicyDecision(allowed=False, reason="SoD violation: preparer cannot approve own execution chain", checks=checks)
    if not any(role in {"tenant_admin", "controller", "cfo"} for role in role_set):
        return PolicyDecision(allowed=False, reason="Approver role insufficient", checks=checks)
    if not approver_user_id.strip():
        return PolicyDecision(allowed=False, reason="Approver identity required", checks=checks)
    checks.append("approval_allowed")
    return PolicyDecision(allowed=True, reason="approval-authorized", checks=checks)


def can_access_field(roles: list[str], field_name: str) -> bool:
    role_set = {role.lower() for role in roles}
    restricted_fields = {"bank_account_number", "tax_id", "salary", "ssn"}
    if field_name not in restricted_fields:
        return True
    return any(role in {"tenant_admin", "cfo", "controller", "governance_admin"} for role in role_set)


def source_acl_allows(source_acl: list[str] | None, source_ref: str) -> bool:
    acl = set(source_acl or [])
    if not acl:
        return True
    if "*" in acl:
        return True
    return source_ref in acl


def abac_allows(attrs: dict | None, action: str, object_type: str) -> bool:
    attrs = attrs or {}
    disallowed_actions = set(attrs.get("disallowed_actions", [])) if isinstance(attrs.get("disallowed_actions", []), list) else set()
    if action in disallowed_actions:
        return False
    allowed_object_types = set(attrs.get("allowed_object_types", [])) if isinstance(attrs.get("allowed_object_types", []), list) else set()
    if allowed_object_types and object_type not in allowed_object_types:
        return False
    return True


def evaluate_action_execution_policy(
    roles: list[str],
    attrs: dict | None,
    action: str,
    object_type: str = "action",
    amount: float | None = None,
    vendor_risk: str | None = None,
    human_approved: bool = False,
    object_id: str | None = None,
    actor_user_id: str | None = None,
) -> PolicyDecision:
    object_context = ObjectContext(
        object_type=object_type,
        object_id=object_id or "",
        amount=amount,
        vendor_risk=vendor_risk,
    )
    return evaluate_object_permission(
        roles=roles,
        action=action,
        object_context=object_context,
        attrs=attrs,
        actor_user_id=actor_user_id,
        human_approved=human_approved,
    )
