from __future__ import annotations

from app.modules.erp.journals.validators.balance_validator import validate_journal_balance
from app.modules.erp.journals.validators.gst_validator import gst_validator
from app.modules.erp.journals.validators.journal_validator import journal_validator


class PostingValidator:
    def validate_for_post(
        self,
        org_id: str,
        *,
        journal: dict,
        lines: list[dict],
    ) -> tuple[float, float]:
        journal_validator.ensure_postable(str(journal.get("journal_status")))
        totals = journal_validator.validate_lines(lines)
        journal_validator.validate_accounts_postable(org_id, lines)
        journal_validator.validate_fiscal_period(
            org_id,
            posting_date=str(journal.get("posting_date")),
            company_id=journal.get("company_id"),
        )
        gst_validator.validate_lines(org_id, lines, company_id=journal.get("company_id"))
        return totals


posting_validator = PostingValidator()
