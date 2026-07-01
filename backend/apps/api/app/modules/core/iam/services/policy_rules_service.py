from app.services.policy_service import PolicyDecision


def evaluate_policy_context_rules(
    *,
    policy_context: dict | None,
    resource: str,
    action: str,
    amount: float | None = None,
    fiscal_period_open: bool | None = None,
    branch_id: str | None = None,
    allowed_branch_ids: list[str] | None = None,
    department_id: str | None = None,
    allowed_department_ids: list[str] | None = None,
) -> PolicyDecision | None:
    ctx = policy_context or {}
    rules = ctx.get("rules")
    if not isinstance(rules, list):
        rules = []

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("resource") and rule.get("resource") != resource:
            continue
        if rule.get("action") and rule.get("action") != action:
            continue
        condition = rule.get("condition") or {}
        if not isinstance(condition, dict):
            continue

        amount_lt = condition.get("amount_lt")
        if amount_lt is not None and amount is not None:
            try:
                if float(amount) >= float(amount_lt):
                    return PolicyDecision(
                        allowed=False,
                        reason="amount_exceeds_policy_rule_limit",
                        checks=["policy_rule_amount_lt_denied"],
                    )
            except (TypeError, ValueError):
                pass

        amount_lte = condition.get("amount_lte")
        if amount_lte is not None and amount is not None:
            try:
                if float(amount) > float(amount_lte):
                    return PolicyDecision(
                        allowed=False,
                        reason="amount_exceeds_policy_rule_limit",
                        checks=["policy_rule_amount_denied"],
                    )
            except (TypeError, ValueError):
                pass

        amount_gte = condition.get("amount_gte")
        if amount_gte is not None and amount is not None:
            try:
                if float(amount) < float(amount_gte):
                    return PolicyDecision(allowed=False, reason="amount_below_policy_rule_minimum", checks=["policy_rule_amount_denied"])
            except (TypeError, ValueError):
                pass

        if condition.get("fiscal_period_open") is True and fiscal_period_open is False:
            return PolicyDecision(allowed=False, reason="fiscal_period_closed", checks=["policy_rule_fiscal_denied"])

        if allowed_department_ids and department_id:
            if department_id not in {str(d) for d in allowed_department_ids}:
                return PolicyDecision(allowed=False, reason="department_scope_denied", checks=["policy_rule_department_denied"])

        branch_outside_limit = condition.get("branch_amount_outside_limit")
        if branch_outside_limit is not None and amount is not None and branch_id:
            try:
                limit = float(branch_outside_limit)
                if float(amount) > limit and allowed_branch_ids and branch_id not in allowed_branch_ids:
                    return PolicyDecision(allowed=False, reason="amount_exceeds_branch_policy_limit", checks=["policy_rule_branch_amount_denied"])
            except (TypeError, ValueError):
                pass

    # Top-level policy_context shortcuts (blueprint examples)
    max_amount = ctx.get("max_approve_amount")
    if max_amount is not None and amount is not None:
        try:
            if float(amount) > float(max_amount):
                return PolicyDecision(allowed=False, reason="amount_exceeds_role_abac_limit", checks=["abac_amount_limit_denied"])
        except (TypeError, ValueError):
            pass

    return None
