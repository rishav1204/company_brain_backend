from __future__ import annotations

from app.modules.erp.journals.ai.journal_generator import build_draft_lines_from_extraction
from app.modules.erp.journals.services.journal_service import journal_service


class AiJournalService:
    """
    AI prepares draft journals only — never posts silently.
    """

    def create_draft_from_extraction(
        self,
        org_id: str,
        *,
        created_by: str | None,
        document_id: str,
        extracted_data: dict,
        posting_date: str,
        journal_type: str = "purchase",
    ) -> dict:
        lines, confidence = build_draft_lines_from_extraction(org_id, extracted_data)
        if confidence.get("requires_review"):
            try:
                from app.services.metrics import metrics_store

                metrics_store.incr_journal_ai_low_confidence()
            except Exception:
                pass
        if not lines:
            raise ValueError("Could not generate journal lines from extraction")

        return journal_service.create_draft(
            org_id,
            created_by=created_by or "ai.journal",
            journal_type=journal_type,
            posting_date=posting_date,
            description=f"AI draft from document {document_id}",
            source_type="document",
            source_id=document_id,
            lines=lines,
            idempotency_key=f"ai-doc:{document_id}",
            ai_confidence=confidence,
        )


ai_journal_service = AiJournalService()
