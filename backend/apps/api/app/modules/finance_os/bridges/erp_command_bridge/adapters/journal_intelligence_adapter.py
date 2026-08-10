from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import JournalIntelligencePort


class JournalIntelligenceAdapter:
    """Finance OS implementation of ERP JournalIntelligencePort — drafts only, never posts."""

    def build_draft_lines_from_extraction(self, org_id: str, extracted_data: dict) -> tuple[list[dict], dict]:
        from app.modules.finance_os.domain_intelligence.journals.journal_generator import (
            build_draft_lines_from_extraction,
        )

        return build_draft_lines_from_extraction(org_id, extracted_data)

    def score_journal_confidence(
        self,
        *,
        ledger_confidence: float,
        gst_confidence: float,
        vendor_confidence: float,
    ) -> dict:
        from app.modules.finance_os.domain_intelligence.journals.confidence_engine import score_journal_confidence

        return score_journal_confidence(
            ledger_confidence=ledger_confidence,
            gst_confidence=gst_confidence,
            vendor_confidence=vendor_confidence,
        )

    def requires_finance_review(self, ai_confidence: dict | None) -> bool:
        from app.modules.finance_os.domain_intelligence.journals.confidence_engine import requires_finance_review

        return requires_finance_review(ai_confidence)

    def detect_journal_anomalies(self, lines: list[dict], *, historical_avg: float | None = None) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.journals.anomaly_checker import detect_journal_anomalies

        return detect_journal_anomalies(lines, historical_avg=historical_avg)

    def suggest_accounts_for_journal(self, extracted_data: dict) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.journals.ledger_suggester import suggest_accounts_for_journal

        return suggest_accounts_for_journal(extracted_data)


_: JournalIntelligencePort | None = None
