from __future__ import annotations


def analyze_evidence(items: list[dict]) -> dict:
    by_type: dict[str, int] = {}
    for item in items or []:
        et = str(item.get("evidence_type") or "unknown")
        by_type[et] = by_type.get(et, 0) + 1
    return {"count": len(items or []), "by_type": by_type, "has_policy": "policy" in by_type, "has_approval": "approval" in by_type}
