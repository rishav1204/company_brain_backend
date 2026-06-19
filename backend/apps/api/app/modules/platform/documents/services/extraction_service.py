from __future__ import annotations

from app.core.config import settings
from app.modules.platform.documents.ai.confidence_engine import confidence_engine
from app.modules.platform.documents.ai.gst_extractor import gst_extractor
from app.modules.platform.documents.ai.invoice_extractor import invoice_extractor
from app.modules.platform.documents.ai.receipt_extractor import extract as receipt_extract
from app.modules.platform.documents.ai.ledger_suggester import suggest_ledger_accounts
from app.modules.platform.documents.ai.anomaly_detector import detect_anomalies
from app.modules.platform.documents.events.document_events import emit_duplicate_detected
from app.modules.platform.documents.repositories.extraction_repository import extraction_repository
from app.modules.platform.documents.services.document_review_workflow_service import document_review_workflow_service
from app.modules.platform.documents.validators.extraction_validator import validate_gst_math


class ExtractionService:
    def extract(self, org_id: str, *, document_id: str, extraction_type: str, text: str) -> dict:
        extraction_type = extraction_type.strip().lower()
        if extraction_type in {"invoice_ocr", "invoice_extraction"}:
            data = invoice_extractor.extract(text)
        elif extraction_type in {"receipt_ocr", "expense_receipt"}:
            data = receipt_extract(text)
        elif extraction_type in {"gst_extraction", "gst_filing"}:
            data = gst_extractor.extract(text)
        else:
            data = {"raw_text": text}
        field_scores = confidence_engine.score_fields(data)
        confidence_score = confidence_engine.aggregate(field_scores)
        data["field_confidence"] = field_scores
        data["ledger_suggestions"] = suggest_ledger_accounts(data)
        data["anomalies"] = detect_anomalies(data)
        if extraction_type in {"invoice_ocr", "invoice_extraction", "gst_extraction", "receipt_ocr", "expense_receipt"}:
            data["gst_math_valid"] = validate_gst_math(data)
        status = "completed" if confidence_score >= settings.document_confidence_threshold else "needs_review"
        row = extraction_repository.create_extraction(
            org_id,
            document_id=document_id,
            extraction_type=extraction_type,
            extracted_data=data,
            confidence_score=confidence_score,
            extraction_status=status,
        )
        if status == "needs_review":
            try:
                document_review_workflow_service.open_review_task(
                    org_id,
                    document_id=document_id,
                    assigned_to=None,
                    reason="low_confidence_extraction",
                    payload={"confidence_score": confidence_score, "threshold": settings.document_confidence_threshold},
                )
            except Exception:
                pass
        return row


extraction_service = ExtractionService()
