from __future__ import annotations

from app.modules.finance_os.invoice_ai.pipelines.invoice_pipeline import invoice_pipeline
from app.modules.finance_os.invoice_ai.repositories.prediction_repository import PredictionRepository
from app.modules.finance_os.invoice_ai.services.confidence_service import confidence_service
from app.modules.finance_os.invoice_ai.services.duplicate_service import duplicate_service
from app.modules.finance_os.invoice_ai.services.extraction_service import extraction_service
from app.modules.finance_os.invoice_ai.services.ledger_suggestion_service import ledger_suggestion_service
from app.modules.finance_os.invoice_ai.services.anomaly_service import anomaly_service
from app.modules.finance_os.invoice_ai.events.invoice_ai_events import emit_invoice_predicted

prediction_repository = PredictionRepository()


class PredictionService:
    def predict(self, org_id: str, *, extraction_id: str) -> dict:
        extraction = extraction_service.get(org_id, extraction_id)
        if not extraction:
            raise ValueError("Extraction not found")
        predictions = ledger_suggestion_service.predict(org_id, extraction=extraction)
        dup = duplicate_service.latest(org_id, extraction_id) or duplicate_service.score(org_id, extraction=extraction)
        anomalies = anomaly_service.list_for_extraction(org_id, extraction_id)
        conf = confidence_service.evaluate(
            extraction=extraction,
            predictions=predictions,
            duplicate_status=str(dup.get("status") or "clean"),
            anomaly_count=len(anomalies),
        )
        confidence_service.update_extraction_band(org_id, extraction_id, conf["confidence_band"])
        payload = {
            "extraction_id": extraction_id,
            "predictions": predictions,
            "overall_confidence": conf["overall_confidence"],
            "confidence_band": conf["confidence_band"],
            "auto_draft_eligible": conf["auto_draft_eligible"],
        }
        emit_invoice_predicted(org_id, payload)
        return payload

    def override_prediction(
        self,
        org_id: str,
        *,
        prediction_id: str,
        suggested_account_id: str | None = None,
        suggested_gst_code: str | None = None,
    ) -> dict | None:
        return prediction_repository.update(
            org_id,
            prediction_id,
            data={
                "suggested_account_id": suggested_account_id,
                "suggested_gst_code": suggested_gst_code,
                "metadata": {"human_override": True},
            },
        )

    def list_suggestions(self, org_id: str, *, extraction_id: str) -> list[dict]:
        return prediction_repository.list_for_extraction(org_id, extraction_id)


prediction_service = PredictionService()
