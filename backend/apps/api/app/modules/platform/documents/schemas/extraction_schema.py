from __future__ import annotations

from pydantic import BaseModel, Field


class OCRRequest(BaseModel):
    document_id: str
    extraction_type: str = Field(default="invoice_ocr", max_length=64)
    force: bool = False


class ExtractionReviewRequest(BaseModel):
    extraction_id: str
    approved: bool
    reviewer_notes: str = Field(default="", max_length=2000)


class ExtractionCorrectionRequest(BaseModel):
    document_id: str
    corrected_data: dict = Field(default_factory=dict)
    reviewer_notes: str = Field(default="", max_length=2000)


class ClassificationRequest(BaseModel):
    document_id: str
    hint: str | None = None
