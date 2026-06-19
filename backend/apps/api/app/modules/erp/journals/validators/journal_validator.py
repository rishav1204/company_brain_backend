from __future__ import annotations

from app.modules.erp.coa.repositories.account_repository import account_repository
from app.modules.erp.fiscal.exceptions import PeriodClosedError
from app.modules.erp.fiscal.services.posting_validation_service import posting_validation_service
from app.modules.erp.gl.validators.double_entry_validator import validate_double_entry

JOURNAL_TYPES = {
    "general",
    "purchase",
    "sales",
    "payment",
    "receipt",
    "contra",
    "adjustment",
    "accrual",
    "reversal",
    "depreciation",
}

EDITABLE_STATUSES = {"draft", "pending_approval"}
POSTABLE_STATUSES = {"approved"}


class JournalValidator:
    def validate_journal_type(self, journal_type: str) -> None:
        if journal_type not in JOURNAL_TYPES:
            raise ValueError(f"Invalid journal_type: {journal_type}")

    def validate_lines(self, lines: list[dict]) -> tuple[float, float]:
        if len(lines) < 2:
            raise ValueError("Journal requires at least 2 lines")
        for line in lines:
            d = float(line.get("debit_amount") or 0)
            c = float(line.get("credit_amount") or 0)
            if d > 0 and c > 0:
                raise ValueError("Journal line cannot have both debit and credit")
            if d == 0 and c == 0:
                raise ValueError("Journal line must have debit or credit amount")
            if not str(line.get("account_id") or "").strip():
                raise ValueError("Journal line missing account_id")
        return validate_double_entry(lines)

    def validate_accounts_postable(self, org_id: str, lines: list[dict]) -> None:
        for line in lines:
            aid = str(line["account_id"])
            acc = account_repository.get(org_id, account_id=aid)
            if not acc or not bool(acc.get("is_active")):
                raise ValueError(f"Account not active: {aid}")
            if not bool(acc.get("is_postable")):
                raise ValueError(f"Account not postable: {aid}")

    def validate_fiscal_period(self, org_id: str, *, posting_date: str, company_id: str | None = None) -> None:
        try:
            posting_validation_service.validate_period_open(org_id, posting_date, company_id=company_id)
        except PeriodClosedError as exc:
            raise ValueError(exc.message) from exc

    def ensure_editable(self, journal_status: str) -> None:
        if journal_status not in EDITABLE_STATUSES:
            raise ValueError(f"Journal status '{journal_status}' is not editable")

    def ensure_postable(self, journal_status: str) -> None:
        if journal_status not in POSTABLE_STATUSES:
            raise ValueError(f"Journal must be approved before posting (status={journal_status})")

    def ensure_reversible(self, journal_status: str) -> None:
        if journal_status != "posted":
            raise ValueError("Only posted journals can be reversed")


journal_validator = JournalValidator()
