from __future__ import annotations

from app.modules.erp.expenses.ai.expense_classifier import classify_expense


def classify(extracted_data: dict) -> dict:
    expense_type = classify_expense(extracted_data)
    return {"expense_type": expense_type, "confidence": 0.75}
