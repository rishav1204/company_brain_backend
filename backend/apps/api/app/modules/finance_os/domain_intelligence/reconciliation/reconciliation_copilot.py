from __future__ import annotations


def answer_reconciliation_question(
    *,
    question: str,
    unreconciled: list[dict] | None = None,
    exceptions: list[dict] | None = None,
    suggestions: list[dict] | None = None,
) -> dict:
    q = (question or "").lower()
    unreconciled = unreconciled or []
    exceptions = exceptions or []
    suggestions = suggestions or []

    if "unreconciled" in q or "why" in q:
        count = len(unreconciled)
        reasons = []
        for tx in unreconciled[:5]:
            reasons.append(f"₹{tx.get('amount')} on {tx.get('transaction_date')} ref={tx.get('transaction_reference') or 'none'}")
        return {
            "answer": f"{count} unreconciled transaction(s). " + ("; ".join(reasons) if reasons else "Import statements or run suggest."),
            "suggestions": ["Run POST /erp/reconciliation/suggest", "Review exceptions queue"],
        }

    if "manual" in q or "review" in q:
        manual = [s for s in suggestions if float(s.get("confidence_score") or 0) < 0.8]
        return {
            "answer": f"{len(manual)} match(es) need manual review (confidence < 80%).",
            "items": manual[:10],
            "suggestions": ["Escalate low-confidence matches", "Assign exceptions"],
        }

    if "exception" in q:
        return {
            "answer": f"{len(exceptions)} open exception(s) in queue.",
            "items": exceptions[:10],
        }

    return {
        "answer": "Ask about unreconciled transactions, manual review queue, or exceptions.",
        "suggestions": ["Why are these transactions unreconciled?", "Show transactions needing manual review"],
    }
