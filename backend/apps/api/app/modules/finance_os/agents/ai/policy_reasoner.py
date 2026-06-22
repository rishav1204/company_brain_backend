from __future__ import annotations


def check(payload: dict, *, org_id: str | None = None, roles: list[str] | None = None) -> list[str]:
    flags: list[str] = []
    if org_id:
        from app.modules.platform.governance.engine.policy_engine import evaluate

        result = evaluate(
            org_id,
            action=str(payload.get("action") or "agent.recommend"),
            attrs=payload,
            roles=roles or [],
            actor_type="agent",
            dry_run=True,
        )
        if not result.allowed:
            flags.append(result.reason or "policy_denied")
        if result.risk_level in {"HIGH", "CRITICAL"}:
            flags.append(f"risk_{result.risk_level.lower()}")
        return flags
    amount = payload.get("amount")
    if amount is not None:
        try:
            if float(amount) >= 500000:
                flags.append("high_amount")
        except (TypeError, ValueError):
            flags.append("invalid_amount")
    vendor_risk = str(payload.get("vendor_risk") or "").lower()
    if vendor_risk in {"high", "critical"}:
        flags.append("vendor_risk")
    if payload.get("gst_filing_requested"):
        flags.append("gst_filing_blocked")
    return flags
