from __future__ import annotations

from datetime import date

from app.modules.erp.vouchers.constants import VOUCHER_TYPE_PREFIX
from app.modules.erp.vouchers.repositories.voucher_sequence_repository import voucher_sequence_repository


class VoucherSequenceService:
    def allocate_number(
        self,
        org_id: str,
        *,
        voucher_type: str,
        voucher_date: str,
        company_id: str | None = None,
    ) -> str:
        prefix = VOUCHER_TYPE_PREFIX.get(voucher_type, "VCH")
        fy = voucher_date[:4] if len(voucher_date) >= 4 else str(date.today().year)
        seq = voucher_sequence_repository.next_sequence(
            org_id, voucher_type=voucher_type, financial_year=fy, company_id=company_id
        )
        return f"{prefix}/{fy}/{seq:06d}"


voucher_sequence_service = VoucherSequenceService()
