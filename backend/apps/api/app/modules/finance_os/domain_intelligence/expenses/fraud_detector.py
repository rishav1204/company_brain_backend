from __future__ import annotations

from app.modules.finance_os.domain_intelligence.expenses.expense_classifier import fraud_score


def detect(extracted_data: dict, *, amount: float) -> dict:
    score = fraud_score(extracted_data, amount=amount)
    return {"fraud_score": score, "requires_review": score >= 40}
