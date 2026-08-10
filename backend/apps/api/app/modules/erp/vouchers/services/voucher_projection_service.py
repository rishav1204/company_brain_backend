from __future__ import annotations

from app.modules.erp.journals.repositories.journal_line_repository import journal_line_repository
from app.modules.erp.vouchers.repositories.voucher_line_repository import voucher_line_repository
from app.modules.erp.vouchers.repositories.voucher_repository import voucher_repository
from app.modules.erp.vouchers.services.voucher_sequence_service import voucher_sequence_service


class VoucherProjectionService:
    def project_from_journal(
        self,
        org_id: str,
        *,
        voucher_type: str,
        reference_type: str,
        reference_id: str,
        source_module: str,
        journal_id: str,
        voucher_date: str,
        narration: str | None,
        company_id: str | None,
        created_by: str | None,
        status: str = "journal_generated",
        total_amount: float | None = None,
    ) -> dict | None:
        try:
            idem = f"projection:{reference_type}:{reference_id}"
            existing = voucher_repository.get_by_idempotency(org_id, idempotency_key=idem)
            if existing:
                return voucher_repository.get(org_id, voucher_id=str(existing["id"]))

            journal_lines = journal_line_repository.list_by_journal(org_id, journal_id=journal_id)
            if not journal_lines:
                return None
            from app.modules.erp.journals.repositories.journal_repository import journal_repository

            journal = journal_repository.get(org_id, journal_id=journal_id) or {}
            journal_branch_id = journal.get("branch_id")
            if total_amount is None:
                total_amount = max(
                    sum(float(l.get("debit_amount") or 0) for l in journal_lines),
                    sum(float(l.get("credit_amount") or 0) for l in journal_lines),
                )
            number = voucher_sequence_service.allocate_number(
                org_id, voucher_type=voucher_type, voucher_date=voucher_date, company_id=company_id
            )
            voucher = voucher_repository.create(
                org_id,
                voucher_number=number,
                voucher_type=voucher_type,
                voucher_date=voucher_date,
                total_amount=float(total_amount or 0),
                narration=narration,
                company_id=company_id,
                branch_id=str(journal_branch_id) if journal_branch_id else None,
                reference_type=reference_type,
                reference_id=reference_id,
                source_module=source_module,
                created_by=created_by,
                idempotency_key=idem,
                metadata={"projected": True},
            )
            vid = str(voucher["id"])
            voucher_line_repository.replace_lines(
                org_id,
                voucher_id=vid,
                lines=[
                    {
                        "account_id": line["account_id"],
                        "debit_amount": line.get("debit_amount") or 0,
                        "credit_amount": line.get("credit_amount") or 0,
                        "narration": line.get("line_description"),
                        "cost_center_id": line.get("cost_center_id"),
                        "tax_code": line.get("tax_code"),
                    }
                    for line in journal_lines
                ],
            )
            voucher_repository.link_journal(org_id, voucher_id=vid, journal_id=journal_id)
            voucher_repository.set_status(org_id, voucher_id=vid, status=status)
            return voucher_repository.get(org_id, voucher_id=vid)
        except Exception:
            return None

    def project_operational(
        self,
        org_id: str,
        *,
        voucher_type: str,
        reference_type: str,
        reference_id: str,
        source_module: str,
        journal_id: str,
        voucher_date: str,
        narration: str | None,
        company_id: str | None,
        created_by: str | None,
        status: str = "posted",
        total_amount: float | None = None,
    ) -> str | None:
        row = self.project_from_journal(
            org_id,
            voucher_type=voucher_type,
            reference_type=reference_type,
            reference_id=reference_id,
            source_module=source_module,
            journal_id=journal_id,
            voucher_date=voucher_date,
            narration=narration,
            company_id=company_id,
            created_by=created_by,
            status=status,
            total_amount=total_amount,
        )
        if not row:
            return None
        vid = str(row["id"])
        try:
            if reference_type == "ap_invoice":
                from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository

                invoice_repository.link_voucher(org_id, invoice_id=reference_id, voucher_id=vid)
            elif reference_type == "ar_invoice":
                from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository

                ar_invoice_repository.link_voucher(org_id, invoice_id=reference_id, voucher_id=vid)
            elif reference_type == "ap_payment":
                from app.modules.erp.accounts_payable.repositories.payment_repository import payment_repository

                payment_repository.link_voucher(org_id, payment_id=reference_id, voucher_id=vid)
        except Exception:
            pass
        return vid


voucher_projection_service = VoucherProjectionService()
