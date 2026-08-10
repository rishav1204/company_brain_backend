from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import ArCollectionsIntelligencePort


class ArCollectionsIntelligenceAdapter:
    """Finance OS implementation of ERP ArCollectionsIntelligencePort."""

    def forecast_collections(self, invoices: list[dict], *, horizons: tuple[int, ...] = (7, 30, 60)) -> dict:
        from app.modules.finance_os.domain_intelligence.ar.collection_predictor import forecast_collections

        return forecast_collections(invoices, horizons=horizons)

    def recommend_collections(self, invoices: list[dict], *, limit: int = 10) -> dict:
        from app.modules.finance_os.domain_intelligence.ar.collection_assistant import recommend_collections

        return recommend_collections(invoices, limit=limit)

    def assess_payment_delay_risk(self, invoice: dict, *, customer_risk_score: float = 0.5) -> dict:
        from app.modules.finance_os.domain_intelligence.ar.payment_risk_model import assess_payment_delay_risk

        return assess_payment_delay_risk(invoice, customer_risk_score=customer_risk_score)

    def score_customer(self, *, invoices: list[dict], receipts: list[dict]) -> dict:
        from app.modules.finance_os.domain_intelligence.ar.customer_scoring import score_customer

        return score_customer(invoices=invoices, receipts=receipts)


_: ArCollectionsIntelligencePort | None = None
