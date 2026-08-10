from __future__ import annotations


def answer_compliance_question(*, question: str, obligations: list[dict] | None = None, dashboard: dict | None = None) -> dict:
    q = question.lower()
    obligations = obligations or []
    dashboard = dashboard or {}
    if "overdue" in q:
        overdue = dashboard.get("overdue") or [o for o in obligations if o.get("status") == "overdue"]
        if not overdue:
            return {"answer": "No overdue obligations.", "items": []}
        lines = [f"- {o.get('title')} due {o.get('due_date')}" for o in overdue[:10]]
        return {"answer": "Overdue obligations:\n" + "\n".join(lines), "items": overdue[:10]}
    if "week" in q or "upcoming" in q or "due" in q:
        upcoming = dashboard.get("upcoming_7d") or [o for o in obligations if o.get("status") in {"upcoming", "due_soon"}]
        if not upcoming:
            return {"answer": "Nothing due in the upcoming window.", "items": []}
        lines = [f"- {o.get('title')} due {o.get('due_date')} ({o.get('compliance_code')})" for o in upcoming[:10]]
        return {"answer": "Upcoming obligations:\n" + "\n".join(lines), "items": upcoming[:10]}
    return {
        "answer": "Ask about overdue items, upcoming deadlines this week, or filing readiness.",
        "suggestions": ["What is due this week?", "Show overdue obligations", "What is my filing readiness score?"],
    }
