import logging

from app.modules.core.iam.repositories import permission_repo, role_repo

logger = logging.getLogger(__name__)


def list_role_names(org_id: str, user_id: str) -> list[str]:
    rows = role_repo.list_user_roles(org_id, user_id)
    return [str(row["role_name"]) for row in rows if row.get("role_name")]


def has_permission(org_id: str, user_id: str, permission_key: str) -> bool:
    if not permission_key:
        return True
    try:
        permissions = permission_repo.list_permissions_for_user(org_id, user_id)
        return permission_key in permissions
    except Exception as exc:
        logger.warning("iam_permission_lookup_failed org_id=%s user_id=%s error=%s", org_id, user_id, exc)
        return False


def merge_policy_context(org_id: str, user_id: str) -> dict:
    """Merge ABAC policy_context from all assigned roles into JWT attrs."""
    rows = role_repo.list_user_roles(org_id, user_id)
    merged: dict = {}
    max_amounts: list[float] = []
    disallowed: set[str] = set()
    for row in rows:
        ctx = row.get("policy_context") or {}
        if not isinstance(ctx, dict):
            continue
        if ctx.get("read_only"):
            merged["read_only"] = True
        if ctx.get("mfa_required"):
            merged["mfa_required"] = True
        max_val = ctx.get("max_approve_amount")
        if max_val is not None:
            try:
                max_amounts.append(float(max_val))
            except (TypeError, ValueError):
                pass
        for action in ctx.get("disallowed_actions", []) or []:
            disallowed.add(str(action))
    # If any role has no cap (null), the user inherits unlimited approval for amount ABAC.
    has_unlimited = any((row.get("policy_context") or {}).get("max_approve_amount") is None for row in rows)
    if not has_unlimited and max_amounts:
        merged["max_approve_amount"] = max(max_amounts)
    if disallowed:
        merged["disallowed_actions"] = sorted(disallowed)

    branch_ids: list[str] = []
    company_ids: list[str] = []
    has_unscoped_assignment = False
    for row in rows:
        branch_id = row.get("branch_id")
        company_id = row.get("company_id")
        if branch_id:
            branch_ids.append(str(branch_id))
        if company_id:
            company_ids.append(str(company_id))
        if not branch_id and not company_id:
            has_unscoped_assignment = True
    if branch_ids and not has_unscoped_assignment:
        merged["allowed_branch_ids"] = sorted(set(branch_ids))
    if company_ids and not has_unscoped_assignment:
        merged["allowed_company_ids"] = sorted(set(company_ids))

    merged_rules: list[dict] = []
    for row in rows:
        ctx = row.get("policy_context") or {}
        if not isinstance(ctx, dict):
            continue
        rules = ctx.get("rules")
        if isinstance(rules, list):
            merged_rules.extend([r for r in rules if isinstance(r, dict)])
    if merged_rules:
        merged["rules"] = merged_rules
    return merged


def permission_key_for_action(action: str, object_type: str = "") -> str:
    action_permission_map = {
        "approve_payment": "payment.approve",
        "post_journal": "journal.post",
        "release_filing": "gst.file",
    }
    if action in action_permission_map:
        return action_permission_map[action]
    if object_type and action:
        candidate = f"{object_type}.{action}"
        if candidate.count(".") == 1:
            return candidate
    return ""


def can_access_sensitive_field(
    org_id: str,
    user_id: str,
    roles: list[str],
    field_name: str,
) -> bool:
    from app.services.policy_service import can_access_field

    field_permission_map = {
        "bank_account_number": "field.bank",
        "tax_id": "field.tax",
        "salary": "field.payroll",
        "ssn": "field.pii",
    }
    perm = field_permission_map.get(field_name)
    if perm:
        try:
            from app.modules.core.iam.services.auth_service import iam_db_enabled

            if iam_db_enabled() and not has_permission(org_id, user_id, perm):
                return False
        except Exception:
            pass
    return can_access_field(roles, field_name)
