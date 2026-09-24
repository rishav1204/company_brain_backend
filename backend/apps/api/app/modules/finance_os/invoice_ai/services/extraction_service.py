from __future__ import annotations

from app.modules.finance_os.invoice_ai.ai.confidence_scorer import confidence_band
from app.modules.finance_os.invoice_ai.ai.entity_normalizer import normalize_gstin, normalize_vendor_name
from app.modules.finance_os.invoice_ai.ai.llm_invoice_extractor import InvoiceExtractor
from app.modules.finance_os.invoice_ai.repositories.extraction_repository import ExtractionRepository
from app.modules.platform.documents.repositories.extraction_repository import (
    extraction_repository as m6_extraction_repository,
)

extraction_repository = ExtractionRepository()


class ExtractionService:
    def __init__(self) -> None:
        self._extractor = InvoiceExtractor()

    def extract_from_document(
        self,
        org_id: str,
        *,
        document_id: str,
        invoice_type: str = "purchase",
        ocr_text: str | None = None,
    ) -> dict:
        m6_row = m6_extraction_repository.latest_extraction(org_id, document_id)
        source_extraction_id = m6_row.get("id") if m6_row else None
        extracted = (m6_row or {}).get("extracted_data") if isinstance((m6_row or {}).get("extracted_data"), dict) else {}

        text = ocr_text or str(extracted.get("raw_text") or extracted.get("raw_text_preview") or "")
        if not text and extracted:
            text = " ".join(str(v) for v in extracted.values() if isinstance(v, str))

        ai_result = self._extractor.extract(org_id, text) if text else {}
        merged = {**extracted, **ai_result}

        vendor_name = merged.get("vendor_name") or merged.get("vendor")
        gstin = normalize_gstin(merged.get("vendor_gstin") or merged.get("gstin"))
        conf = float(merged.get("extraction_confidence") or merged.get("confidence_score") or 0)
        if conf <= 1:
            conf_pct = conf * 100
        else:
            conf_pct = conf

        row = extraction_repository.create(
            org_id,
            data={
                "document_id": document_id,
                "source_extraction_id": source_extraction_id,
                "invoice_number": merged.get("invoice_number") or merged.get("invoice"),
                "vendor_name": vendor_name,
                "vendor_name_normalized": normalize_vendor_name(str(vendor_name) if vendor_name else None),
                "vendor_gstin": gstin,
                "invoice_date": merged.get("invoice_date") or merged.get("date"),
                "due_date": merged.get("due_date"),
                "taxable_amount": float(merged.get("taxable_amount") or merged.get("subtotal") or 0),
                "gst_amount": float(merged.get("gst_amount") or 0),
                "total_amount": float(merged.get("total_amount") or merged.get("total") or 0),
                "extraction_confidence": conf_pct,
                "confidence_band": confidence_band(conf_pct),
                "invoice_type": invoice_type,
                "metadata": {"method": merged.get("method"), "line_items": merged.get("line_items") or []},
            },
        )
        return row

    def get(self, org_id: str, extraction_id: str) -> dict | None:
        return extraction_repository.get(org_id, extraction_id)

    def latest_for_document(self, org_id: str, document_id: str) -> dict | None:
        return extraction_repository.latest_for_document(org_id, document_id)

    def list_review_queue(self, org_id: str, *, limit: int = 50) -> list[dict]:
        return extraction_repository.list_review_queue(org_id, limit=limit)


extraction_service = ExtractionService()
