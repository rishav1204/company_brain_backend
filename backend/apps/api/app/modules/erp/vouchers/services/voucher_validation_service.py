from __future__ import annotations

from app.modules.erp.fiscal.services.posting_validation_service import posting_validation_service
from app.modules.erp.journals.validators.journal_validator import journal_validator
from app.modules.erp.vouchers.constants import VOUCHER_TYPES


class VoucherValidationService:
    def validate(self, org_id: str, *, voucher: dict, lines: list[dict]) -> None:
        vtype = str(voucher.get("voucher_type") or "")
        if vtype not in VOUCHER_TYPES:
            raise ValueError(f"Invalid voucher_type: {vtype}")
        if not lines:
            raise ValueError("Voucher requires at least one line")
        journal_validator.validate_lines(lines)
        journal_validator.validate_accounts_postable(org_id, lines)
        posting_validation_service.validate_period_open(
            org_id,
            str(voucher.get("voucher_date")),
            company_id=voucher.get("company_id"),
        )
        if vtype == "journal":
            journal_validator.validate_lines(lines)


voucher_validation_service = VoucherValidationService()
