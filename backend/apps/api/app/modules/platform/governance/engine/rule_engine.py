from __future__ import annotations

from app.modules.platform.governance.repositories.policy_repository import policy_repository
from app.modules.platform.governance.engine import policy_cache_engine


def load_rules(org_id: str) -> list[dict]:
    cached = policy_cache_engine.get_cached(org_id, "rules")
    if cached is not None:
        return cached
    rules = policy_repository.list_active(org_id)
    policy_cache_engine.set_cached(org_id, "rules", rules)
    return rules


def rule_applies(rule: dict, action: str, attrs: dict) -> bool:
    conditions = rule.get("conditions") or {}
    if conditions.get("action") and conditions["action"] != action:
        return False
    amount = float(attrs.get("amount", 0) or 0)
    if "amount_gt" in conditions and amount <= float(conditions["amount_gt"]):
        return False
    if conditions.get("closed_period") and attrs.get("fiscal_period_open") is False:
        return True
    if conditions.get("enforce"):
        return True
    if conditions.get("day_of_month_gt"):
        from datetime import datetime, timezone

        if datetime.now(timezone.utc).day <= int(conditions["day_of_month_gt"]):
            return False
        return True
    return bool(conditions)


def evaluate_rule(rule: dict, attrs: dict, roles: list[str]) -> str | None:
    actions = rule.get("actions") or {}
    if actions.get("block"):
        if rule.get("policy_type") == "fiscal" and attrs.get("fiscal_period_open") is False:
            return "Fiscal period is closed"
        if rule.get("policy_type") == "approval":
            required = actions.get("require_role")
            if required and required not in roles:
                return f"Requires role: {required}"
    return None


def evaluate_rules(org_id: str, *, action: str, attrs: dict, roles: list[str]) -> list[dict]:
    violations: list[dict] = []
    for rule in load_rules(org_id):
        if not rule_applies(rule, action, attrs):
            continue
        blocked = evaluate_rule(rule, attrs, roles)
        if blocked:
            violations.append(
                {
                    "type": rule.get("policy_key") or rule.get("policy_code", "policy"),
                    "policy_type": rule.get("policy_type"),
                    "message": blocked,
                    "severity": "high",
                }
            )
    return violations
