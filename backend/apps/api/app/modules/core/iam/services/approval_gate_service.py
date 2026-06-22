"""Unified human-approval gate (IAM + legacy)."""

from __future__ import annotations

from app.modules.core.iam.services.auth_service import iam_db_enabled


_CRITICAL_ACTIONS = frozenset(
    {
        "approve",
        "approve_payment",
        "post_journal",
        "release_filing",
        "payment.approve",
        "journal.post",
        "gst.file",
        "invoice.approve",
        "execute",
        "payment.execute",
    }
)


def is_critical_action(action: str) -> bool:
    normalized = action.strip().lower()
    if normalized in _CRITICAL_ACTIONS:
        return True
    return any(normalized.endswith(suffix) for suffix in (".approve", ".post", ".execute", ".file"))


def requires_human_approval(
    *,
    action: str,
    amount: float | None = None,
    vendor_risk: str | None = None,
    attrs: dict | None = None,
) -> bool:
    """Whether a second human approval step is required before execution."""
    attrs = attrs or {}
    if is_critical_action(action):
        return True
    if vendor_risk is not None and str(vendor_risk).lower() == "high":
        return True
    if amount is None:
        return False
    if iam_db_enabled() and isinstance(attrs, dict):
        max_amount = attrs.get("max_approve_amount")
        if max_amount is not None:
            try:
                return float(amount) > float(max_amount)
            except (TypeError, ValueError):
                pass
        rules = attrs.get("rules")
        if isinstance(rules, list):
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                cond = rule.get("condition") or {}
                if rule.get("action") == action or not rule.get("action"):
                    for key in ("amount_lte", "amount_lt"):
                        limit = cond.get(key)
                        if limit is not None:
                            try:
                                if float(amount) > float(limit):
                                    return True
                            except (TypeError, ValueError):
                                pass
    return False


def pending_approval_response_reason(decision_reason: str) -> bool:
    return decision_reason in {"human_approval_required", "approval_required"}
