from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import BankingIntelligencePort


class BankingIntelligenceAdapter:
    """Finance OS implementation of ERP BankingIntelligencePort."""

    def detect_payment_anomalies(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.payments.anomaly_detector import detect_payment_anomalies

        return detect_payment_anomalies(**kwargs)

    def classify_transaction(self, narration: str) -> str:
        from app.modules.finance_os.domain_intelligence.payments.anomaly_detector import classify_transaction

        return classify_transaction(narration)

    def detect_transaction_anomalies(self, *, transactions: list[dict]) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.payments.anomaly_detector import detect_transaction_anomalies

        return detect_transaction_anomalies(transactions=transactions)

    def answer_banking_question(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.banking.banking_copilot import answer_banking_question

        return answer_banking_question(**kwargs)

    def classify_narration(self, narration: str) -> dict:
        from app.modules.finance_os.domain_intelligence.banking.banking_copilot import classify_narration

        return classify_narration(narration)


_: BankingIntelligencePort | None = None
