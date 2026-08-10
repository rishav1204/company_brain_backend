from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import ApRiskIntelligencePort


class ApRiskIntelligenceAdapter:
    """Finance OS implementation of ERP ApRiskIntelligencePort — not imported by ERP code."""

    def classify_vendor_from_extraction(self, extracted_data: dict) -> dict:
        from app.modules.finance_os.invoice_ai.review.vendor_classifier import classify_vendor_from_extraction

        return classify_vendor_from_extraction(extracted_data)

    def review_invoice_extraction(self, extracted_data: dict, *, vendor_gstin: str | None = None) -> dict:
        from app.modules.finance_os.invoice_ai.review.invoice_reviewer import review_invoice_extraction

        return review_invoice_extraction(extracted_data, vendor_gstin=vendor_gstin)

    def duplicate_signals(self, dup_check: dict) -> dict:
        from app.modules.finance_os.invoice_ai.review.duplicate_signals import detect_duplicate_signals

        return detect_duplicate_signals(dup_check)

    def suggest_ledger_accounts(self, extracted_data: dict, *, org_id: str | None = None) -> list[dict]:
        from app.modules.platform.documents.ai.ledger_suggester import suggest_ledger_accounts

        return suggest_ledger_accounts(extracted_data, org_id=org_id)

    def assess_vendor_risk(
        self,
        org_id: str,
        *,
        vendor_id: str,
        invoices: list[dict],
        payments: list[dict],
    ) -> dict:
        from app.modules.finance_os.domain_intelligence.ap.vendor_risk import assess_vendor_risk

        return assess_vendor_risk(org_id, vendor_id=vendor_id, invoices=invoices, payments=payments)

    def rank_invoices_for_payment(self, invoices: list[dict], *, as_of: str | None = None) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.ap.payment_optimizer import rank_invoices_for_payment

        return rank_invoices_for_payment(invoices, as_of=as_of)

    def priority_score(self, invoice: dict, *, as_of: str | None = None) -> float:
        from app.modules.finance_os.domain_intelligence.ap.payment_optimizer import priority_score

        return priority_score(invoice, as_of=as_of)

    def forecast_cash_requirement(self, outstanding_invoices: list[dict], *, horizon_days: int = 30) -> dict:
        from app.modules.finance_os.forecasting.engine.ap_cash_requirement import forecast_cash_requirement

        return forecast_cash_requirement(outstanding_invoices, horizon_days=horizon_days)


_: ApRiskIntelligencePort | None = None
