from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import ExpenseIntelligencePort


class ExpenseIntelligenceAdapter:
    """Finance OS implementation of ERP ExpenseIntelligencePort — not imported by ERP code."""

    def classify_expense(self, extracted_data: dict) -> str:
        from app.modules.finance_os.domain_intelligence.expenses.expense_classifier import classify_expense

        return classify_expense(extracted_data)

    def fraud_score(self, extracted_data: dict, *, amount: float) -> float:
        from app.modules.finance_os.domain_intelligence.expenses.expense_classifier import fraud_score

        return fraud_score(extracted_data, amount=amount)

    def detect_fraud(self, extracted_data: dict, *, amount: float) -> dict:
        from app.modules.finance_os.domain_intelligence.expenses.fraud_detector import detect

        return detect(extracted_data, amount=amount)

    def classify_duplicate(self, extracted_data: dict) -> dict:
        from app.modules.finance_os.domain_intelligence.expenses.duplicate_detector import classify

        return classify(extracted_data)

    def analyze_spend(self, org_id: str, *, employee_id: str | None = None) -> dict:
        from app.modules.finance_os.domain_intelligence.expenses.spend_analyzer import analyze_spend

        return analyze_spend(org_id, employee_id=employee_id)


_: ExpenseIntelligencePort | None = None
