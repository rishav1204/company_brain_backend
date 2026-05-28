from __future__ import annotations

from app.modules.platform.documents.repositories.document_repository import document_repository
from app.modules.platform.documents.repositories.extraction_repository import extraction_repository


class ClassificationService:
    def classify(self, org_id: str, *, document_id: str, hint: str | None = None) -> dict:
        doc = document_repository.get_document(org_id, document_id)
        if not doc:
            raise ValueError("Document not found")
        if hint:
            label = hint.strip().lower()
            confidence = 0.9
        else:
            # Hybrid: mime + filename + OCR/extraction text heuristics (phase 1)
            file_name = str(doc.get("file_name", "")).lower()
            mime = str(doc.get("mime_type", "")).lower()
            latest = extraction_repository.latest_extraction(org_id, document_id) or {}
            preview = str((latest.get("extracted_data") or {}).get("raw_text_preview", "")).lower()
            combined = " ".join([file_name, mime, preview])
            if "gst" in combined and ("return" in combined or "gstr" in combined):
                label, confidence = "gst_filing", 0.85
            elif "bank" in combined and ("statement" in combined or "ifsc" in combined):
                label, confidence = "bank_statement", 0.8
            elif "receipt" in combined:
                label, confidence = "receipt", 0.8
            elif "contract" in combined or "agreement" in combined:
                label, confidence = "contract", 0.78
            elif "kyc" in combined or "pan" in combined or "aadhaar" in combined:
                label, confidence = "vendor_kyc", 0.8
            elif "payment" in combined and ("proof" in combined or "utr" in combined):
                label, confidence = "payment_proof", 0.78
            else:
                label, confidence = "invoice", 0.75
        return extraction_repository.create_classification(
            org_id,
            document_id=document_id,
            classification=label,
            confidence_score=confidence,
            classified_by="ai",
        )


classification_service = ClassificationService()
