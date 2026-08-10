from __future__ import annotations

from typing import Any

from app.modules.erp.ports.intelligence_registry import InvoiceIntelligencePort


class InvoiceIntelligenceAdapter:
    """Finance OS implementation of ERP InvoiceIntelligencePort — not imported by ERP code."""

    def run_pipeline(self, org_id: str, *, document_id: str, invoice_type: str = "purchase") -> dict:
        from app.modules.finance_os.invoice_ai.pipelines.invoice_pipeline import invoice_pipeline

        return invoice_pipeline.run(org_id, document_id=document_id, invoice_type=invoice_type)

    def get_extraction(self, org_id: str, extraction_id: str) -> dict | None:
        from app.modules.finance_os.invoice_ai.services.extraction_service import extraction_service

        return extraction_service.get(org_id, extraction_id)

    def latest_duplicate(self, org_id: str, extraction_id: str) -> dict | None:
        from app.modules.finance_os.invoice_ai.services.duplicate_service import duplicate_service

        return duplicate_service.latest(org_id, extraction_id)

    def list_anomalies(self, org_id: str, extraction_id: str) -> list[dict]:
        from app.modules.finance_os.invoice_ai.services.anomaly_service import anomaly_service

        return anomaly_service.list_for_extraction(org_id, extraction_id)

    def list_suggestions(self, org_id: str, *, extraction_id: str) -> list[dict]:
        from app.modules.finance_os.invoice_ai.services.prediction_service import prediction_service

        return prediction_service.list_suggestions(org_id, extraction_id=extraction_id)

    def list_predictions_for_extraction(self, org_id: str, extraction_id: str) -> list[dict]:
        from app.modules.finance_os.invoice_ai.repositories.prediction_repository import prediction_repository

        return prediction_repository.list_for_extraction(org_id, extraction_id)

    def evaluate_confidence(
        self,
        *,
        extraction: dict,
        predictions: list[dict],
        duplicate_status: str,
        anomaly_count: int,
    ) -> dict:
        from app.modules.finance_os.invoice_ai.services.confidence_service import confidence_service

        return confidence_service.evaluate(
            extraction=extraction,
            predictions=predictions,
            duplicate_status=duplicate_status,
            anomaly_count=anomaly_count,
        )

    def link_prediction(self, org_id: str, prediction_id: str, *, ap_invoice_id: str) -> Any:
        from app.modules.finance_os.invoice_ai.repositories.prediction_repository import prediction_repository

        return prediction_repository.link_ap_invoice(org_id, prediction_id, ap_invoice_id=ap_invoice_id)


# Typing helper — runtime duck-typing sufficient for Protocol
_: InvoiceIntelligencePort | None = None
