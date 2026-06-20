from __future__ import annotations

from app.modules.finance_os.memory.ai.pattern_detector import detect_recurring_patterns
from app.modules.finance_os.memory.repositories.entry_repository import entry_repository


def org_insights(org_id: str) -> dict:
    rows = entry_repository.list_active(org_id, limit=500)
    patterns = detect_recurring_patterns(rows)
    top_vendors = [r for r in rows if r.get("memory_type") == "vendor"][:5]
    risks = [r for r in rows if r.get("memory_type") in {"compliance", "treasury"}][:5]
    return {
        "patterns": patterns,
        "top_vendor_behaviors": top_vendors,
        "risk_signals": risks,
        "total_active": len(rows),
    }
