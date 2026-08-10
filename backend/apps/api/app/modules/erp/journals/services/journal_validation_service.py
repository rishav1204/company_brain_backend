from __future__ import annotations

from app.modules.erp.journals.validators.posting_validator import posting_validator
from app.modules.erp.journals.validators.journal_validator import journal_validator
from app.modules.erp.ports.intelligence_registry import intelligence_registry


class JournalValidationService:
    def validate_submit(self, org_id: str, *, journal: dict, lines: list[dict]) -> None:
        journal_validator.validate_lines(lines)
        journal_validator.validate_accounts_postable(org_id, lines)
        journal_validator.validate_fiscal_period(
            org_id,
            posting_date=str(journal.get("posting_date")),
            company_id=journal.get("company_id"),
        )

    def validate_approve(self, org_id: str, *, journal: dict, lines: list[dict]) -> None:
        self.validate_submit(org_id, journal=journal, lines=lines)
        self.ensure_ai_reviewed(journal)

    def validate_post(self, org_id: str, *, journal: dict, lines: list[dict]) -> tuple[float, float]:
        self.ensure_ai_reviewed(journal)
        return posting_validator.validate_for_post(org_id, journal=journal, lines=lines)

    def ensure_ai_reviewed(self, journal: dict) -> None:
        confidence = journal.get("ai_confidence") if isinstance(journal.get("ai_confidence"), dict) else {}
        if intelligence_registry.journal().requires_finance_review(confidence):
            raise ValueError(
                "AI confidence below threshold; finance review required before approve/post. "
                "Edit journal lines or mark as reviewed."
            )


journal_validation_service = JournalValidationService()
