from __future__ import annotations

from app.modules.finance_os.domain_intelligence.payments.anomaly_detector import classify_transaction


def answer_banking_question(*, question: str, payments: list[dict] | None = None, transactions: list[dict] | None = None) -> dict:
    q = question.lower()
    payments = payments or []
    transactions = transactions or []
    if "large" in q and "payment" in q:
        large = [p for p in payments if float(p.get("amount") or 0) >= 100_000]
        lines = [f"- {p.get('payment_reference')} ₹{p.get('amount'):,.2f}" for p in large[:10]]
        return {"answer": "Large payments:\n" + ("\n".join(lines) if lines else "None today."), "items": large[:10]}
    if "unreconciled" in q or "credit" in q:
        credits = [t for t in transactions if t.get("transaction_type") == "credit" and t.get("reconciliation_status") != "matched"]
        return {"answer": f"{len(credits)} unreconciled credit transactions.", "items": credits[:10]}
    return {"answer": "Ask about large payments, unreconciled credits, or transaction classification.", "suggestions": ["Show large payments today", "Unreconciled credits"]}


def classify_narration(narration: str) -> dict:
    return {"category": classify_transaction(narration), "narration": narration}
