from __future__ import annotations

from app.modules.erp.journals.validators.journal_validator import journal_validator


class ReversalValidator:
    def ensure_reversible(self, journal_status: str) -> None:
        journal_validator.ensure_reversible(journal_status)


reversal_validator = ReversalValidator()
