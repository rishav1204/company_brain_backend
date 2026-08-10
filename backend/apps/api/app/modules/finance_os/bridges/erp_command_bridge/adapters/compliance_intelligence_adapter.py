from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import ComplianceIntelligencePort


class ComplianceIntelligenceAdapter:
    """Finance OS implementation of ERP ComplianceIntelligencePort."""

    def compute_risk_score(self, *, overdue: list[dict], escalations: list[dict], exposure: float) -> int:
        from app.modules.finance_os.domain_intelligence.compliance.risk_detector import compute_risk_score

        return compute_risk_score(overdue=overdue, escalations=escalations, exposure=exposure)

    def detect_risks(self, *, obligations: list[dict], escalations: list[dict], exposure: float) -> dict:
        from app.modules.finance_os.domain_intelligence.compliance.risk_detector import detect_risks

        return detect_risks(obligations=obligations, escalations=escalations, exposure=exposure)

    def predict_notice_risk(self, *, risk_flags: list[dict]) -> dict:
        from app.modules.finance_os.domain_intelligence.compliance.notice_predictor import predict_notice_risk

        return predict_notice_risk(risk_flags=risk_flags)

    def filing_readiness_score(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.compliance.filing_advisor import filing_readiness_score

        return filing_readiness_score(**kwargs)

    def answer_compliance_question(self, **kwargs) -> dict:
        from app.modules.finance_os.domain_intelligence.compliance.compliance_assistant import (
            answer_compliance_question,
        )

        return answer_compliance_question(**kwargs)


_: ComplianceIntelligencePort | None = None
