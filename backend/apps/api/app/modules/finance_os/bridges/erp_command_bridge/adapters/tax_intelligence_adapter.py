from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import TaxIntelligencePort


class TaxIntelligenceAdapter:
    """Finance OS implementation of ERP TaxIntelligencePort."""

    def recommend_section(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.tax.tds_section_recommender import recommend_section

        return recommend_section(**kwargs)

    def detect_tds_errors(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.tax.tds_error_detector import detect_tds_errors

        return detect_tds_errors(**kwargs)

    def review_vendor_quarter(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.tax.tds_error_detector import review_vendor_quarter

        return review_vendor_quarter(**kwargs)

    def review_return_payload(self, *, payload: dict, form_type: str) -> dict:
        from app.modules.finance_os.domain_intelligence.tax.tds_return_reviewer import review_return_payload

        return review_return_payload(payload=payload, form_type=form_type)

    def answer_tds_question(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.tax.tds_copilot import answer_tds_question

        return answer_tds_question(**kwargs)

    def detect_mismatches(self, our_tx: dict, gstr2b_row: dict) -> dict:
        from app.modules.finance_os.domain_intelligence.tax.mismatch_detector import detect_mismatches

        return detect_mismatches(our_tx, gstr2b_row)

    def answer_gst_question(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.tax.gst_copilot import answer_gst_question

        return answer_gst_question(**kwargs)

    def assess_tax_risks(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.tax.tax_risk_engine import assess_tax_risks

        return assess_tax_risks(**kwargs)

    def vendor_mismatch_report(self, reconciliations: list[dict]) -> dict:
        from app.modules.finance_os.domain_intelligence.tax.compliance_assistant import vendor_mismatch_report

        return vendor_mismatch_report(reconciliations)

    def answer_compliance_question(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.tax.compliance_assistant import answer_compliance_question

        return answer_compliance_question(**kwargs)

    def analyze_notice(self, *, notice_type: str, metadata: dict) -> dict:
        from app.modules.finance_os.domain_intelligence.tax.notice_analyzer import analyze_notice

        return analyze_notice(notice_type=notice_type, metadata=metadata)


_: TaxIntelligencePort | None = None
