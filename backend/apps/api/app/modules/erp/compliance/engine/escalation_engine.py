from __future__ import annotations


def next_escalation_level(
    current_level: int,
    levels: list[str] | None = None,
    *,
    org_id: str | None = None,
) -> tuple[int, str | None]:
    chain = levels
    if not chain:
        try:
            from app.modules.platform.regulatory.services.regulatory_resolver import (
                regulatory_resolver,
            )

            raw = regulatory_resolver.resolve_param(
                "compliance.escalation_levels",
                org_id=org_id,
                required=False,
                default=["assignee", "manager", "finance_head", "cfo"],
            )
            if isinstance(raw, list):
                chain = [str(x) for x in raw]
            elif isinstance(raw, dict) and isinstance(raw.get("levels"), list):
                chain = [str(x) for x in raw["levels"]]
            else:
                chain = ["assignee", "manager", "finance_head", "cfo"]
        except Exception:
            chain = ["assignee", "manager", "finance_head", "cfo"]
    if current_level >= len(chain):
        return current_level, None
    idx = min(current_level, len(chain) - 1)
    return idx + 1, chain[idx]


def should_escalate(*, status: str, due_date, today) -> bool:
    from datetime import date

    if status in {"completed", "waived"}:
        return False
    if isinstance(due_date, str):
        due_date = date.fromisoformat(due_date[:10])
    return due_date < (today or date.today())
