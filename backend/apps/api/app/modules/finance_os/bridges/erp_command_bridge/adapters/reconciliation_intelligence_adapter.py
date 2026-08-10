from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import ReconciliationIntelligencePort


class ReconciliationIntelligenceAdapter:
    """Finance OS implementation of ERP ReconciliationIntelligencePort."""

    def suggest_matches(
        self,
        bank_tx: dict,
        ledger_entries: list[dict],
        *,
        subledger_candidates: list[dict] | None = None,
        rules: list[dict] | None = None,
        limit: int = 5,
    ) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.reconciliation.suggestion_engine import suggest_matches

        return suggest_matches(
            bank_tx,
            ledger_entries,
            subledger_candidates=subledger_candidates,
            rules=rules,
            limit=limit,
        )

    def score_breakdown(self, match_result: dict) -> dict:
        from app.modules.finance_os.domain_intelligence.reconciliation.confidence_scorer import score_breakdown

        return score_breakdown(match_result)

    def classify_narration(self, narration: str) -> str:
        from app.modules.finance_os.domain_intelligence.reconciliation.transaction_classifier import classify_narration

        return classify_narration(narration)

    def detect_anomalies(
        self,
        *,
        bank_tx: dict,
        candidates: list[dict] | None = None,
        history_amounts: list[float] | None = None,
    ) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.reconciliation.anomaly_detector import detect_anomalies

        return detect_anomalies(bank_tx=bank_tx, candidates=candidates, history_amounts=history_amounts)

    def answer_question(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.reconciliation.reconciliation_copilot import (
            answer_reconciliation_question,
        )

        return answer_reconciliation_question(**kwargs)


_: ReconciliationIntelligencePort | None = None
