from __future__ import annotations

from app.modules.finance_os.invoice_ai.events.invoice_ai_events import (
    emit_anomaly_detected,
    emit_duplicate_scored,
    emit_invoice_extracted,
    emit_invoice_predicted,
    emit_pipeline_completed,
)
from app.modules.finance_os.invoice_ai.services.anomaly_service import anomaly_service
from app.modules.finance_os.invoice_ai.services.confidence_service import confidence_service
from app.modules.finance_os.invoice_ai.services.duplicate_service import duplicate_service
from app.modules.finance_os.invoice_ai.services.extraction_service import extraction_service
from app.modules.finance_os.invoice_ai.services.ledger_suggestion_service import ledger_suggestion_service


class InvoicePipeline:
    def run(
        self,
        org_id: str,
        *,
        document_id: str,
        invoice_type: str = "purchase",
        ocr_text: str | None = None,
    ) -> dict:
        extraction = extraction_service.extract_from_document(
            org_id,
            document_id=document_id,
            invoice_type=invoice_type,
            ocr_text=ocr_text,
        )
        emit_invoice_extracted(
            org_id,
            {
                "extraction_id": extraction["id"],
                "document_id": document_id,
                "confidence_band": extraction.get("confidence_band"),
            },
        )

        full_extraction = extraction_service.get(org_id, extraction["id"]) or extraction
        predictions = ledger_suggestion_service.predict(org_id, extraction=full_extraction)
        dup = duplicate_service.score(org_id, extraction=full_extraction)
        anomalies = anomaly_service.detect_and_persist(
            org_id,
            extraction=full_extraction,
            duplicate_status=str(dup.get("status") or "clean"),
        )

        conf = confidence_service.evaluate(
            extraction=full_extraction,
            predictions=predictions,
            duplicate_status=str(dup.get("status") or "clean"),
            anomaly_count=len(anomalies),
        )
        confidence_service.update_extraction_band(org_id, extraction["id"], conf["confidence_band"])

        emit_invoice_predicted(
            org_id,
            {
                "extraction_id": extraction["id"],
                "document_id": document_id,
                "predictions": predictions,
                "overall_confidence": conf["overall_confidence"],
                "confidence_band": conf["confidence_band"],
                "auto_draft_eligible": conf["auto_draft_eligible"],
            },
        )
        emit_duplicate_scored(
            org_id,
            {"extraction_id": extraction["id"], "document_id": document_id, **dup},
        )
        if anomalies:
            emit_anomaly_detected(
                org_id,
                {"extraction_id": extraction["id"], "document_id": document_id, "anomalies": anomalies},
            )

        result = {
            "extraction_id": extraction["id"],
            "document_id": document_id,
            "confidence_band": conf["confidence_band"],
            "duplicate_status": dup.get("status", "clean"),
            "anomaly_count": len(anomalies),
            "auto_draft_eligible": conf["auto_draft_eligible"],
            "overall_confidence": conf["overall_confidence"],
        }
        emit_pipeline_completed(org_id, result)
        return result


invoice_pipeline = InvoicePipeline()
