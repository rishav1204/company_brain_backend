from __future__ import annotations

from app.modules.finance_os.analytics.repositories.insight_repository import insight_repository


def suggest(org_id: str, *, limit: int = 5) -> list[dict]:
    insights = insight_repository.list(org_id, limit=limit)
    actions = []
    for ins in insights:
        actions.append({
            "insight_id": ins.get("id"),
            "title": ins.get("title"),
            "recommended_action": _action_for(ins),
            "severity": ins.get("severity"),
        })
    return actions


def _action_for(ins: dict) -> str:
    itype = str(ins.get("insight_type") or "")
    if itype == "collections":
        return "Review top overdue customers and escalate collections workflow."
    if itype == "treasury":
        return "Review cash forecast and upcoming obligations with treasury team."
    if itype == "close":
        return "Investigate close bottlenecks in PERIOD_CLOSE workflow stages."
    if itype == "forecast":
        return "Recalibrate forecast assumptions and review actual vs forecast drivers."
    if itype == "profitability":
        return "Analyze expense and revenue drivers with department heads."
    return "Review supporting reports and assign owner for follow-up."
