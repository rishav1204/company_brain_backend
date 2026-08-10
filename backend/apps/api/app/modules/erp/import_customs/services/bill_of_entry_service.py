from __future__ import annotations

from app.core.config import settings
from app.modules.erp.accounts_payable.engine.account_resolver import (
    resolve_account_by_code,
    resolve_account_by_type,
    resolve_expense_account,
    resolve_gst_account,
)
from app.modules.erp.import_customs.repositories.bill_of_entry_repository import bill_of_entry_repository
from app.modules.erp.journals.services.approval_service import approval_service as journal_approval_service
from app.modules.erp.journals.services.journal_service import journal_service
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.modules.erp.security.company_resolution_service import company_resolution_service
from app.modules.erp.security.company_scope import require_company_id_for_erp_write


def _resolve_customs_duty_account(org_id: str, company_id: str | None) -> str | None:
    return (
        resolve_account_by_type(org_id, "customs_duty")
        or resolve_account_by_code(org_id, "5205")
        or resolve_expense_account(org_id)
    )


def _resolve_import_inventory_account(org_id: str) -> str | None:
    return resolve_account_by_type(org_id, "inventory") or resolve_account_by_code(org_id, "1300")


def _resolve_payable_account(org_id: str, vendor_id: str | None) -> str | None:
    if vendor_id:
        from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository

        vendor = vendor_repository.get(org_id, vendor_id=vendor_id)
        if vendor and vendor.get("payable_account_id"):
            return str(vendor["payable_account_id"])
    return resolve_account_by_type(org_id, "payable") or resolve_account_by_code(org_id, "2100")


class BillOfEntryService:
    def create_boe(
        self,
        org_id: str,
        *,
        boe_number: str,
        boe_date: str,
        assessable_value: float,
        customs_duty: float = 0,
        igst_import: float = 0,
        company_id: str | None = None,
        branch_id: str | None = None,
        port_code: str | None = None,
        vendor_id: str | None = None,
        po_id: str | None = None,
        currency_code: str = "INR",
        exchange_rate: float = 1.0,
        metadata: dict | None = None,
    ) -> dict:
        if assessable_value < 0 or customs_duty < 0 or igst_import < 0:
            raise ValueError("BOE amounts cannot be negative")
        if settings.erp_require_company_id:
            company_id = company_resolution_service.resolve_for_write(
                org_id, company_id=company_id, operation="import_customs.boe.create"
            )
        elif company_id:
            require_company_id_for_erp_write(
                org_id=org_id, company_id=company_id, operation="import_customs.boe.create"
            )
        return bill_of_entry_repository.create(
            org_id,
            boe_number=boe_number,
            boe_date=boe_date,
            assessable_value=assessable_value,
            customs_duty=customs_duty,
            igst_import=igst_import,
            company_id=company_id,
            branch_id=branch_id,
            port_code=port_code,
            vendor_id=vendor_id,
            po_id=po_id,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            metadata=metadata,
        )

    def get_boe(self, org_id: str, *, boe_id: str) -> dict:
        row = bill_of_entry_repository.get(org_id, boe_id=boe_id)
        if not row:
            raise ValueError("Bill of entry not found")
        return row

    def list_boes(self, org_id: str, *, status: str | None = None, limit: int = 100) -> list[dict]:
        return bill_of_entry_repository.list(org_id, status=status, limit=limit)

    def post_boe(self, org_id: str, *, boe_id: str, actor_id: str | None = None) -> dict:
        boe = bill_of_entry_repository.get(org_id, boe_id=boe_id)
        if not boe:
            raise ValueError("Bill of entry not found")
        if str(boe.get("status")) == "posted":
            return {**boe, "idempotent": True}

        company_id = boe.get("company_id")
        assessable = float(boe.get("assessable_value") or 0)
        customs = float(boe.get("customs_duty") or 0)
        igst = float(boe.get("igst_import") or 0)
        total = round(assessable + customs + igst, 2)
        if total <= 0:
            raise ValueError("BOE has no amounts to post")

        inventory_id = _resolve_import_inventory_account(org_id)
        customs_id = _resolve_customs_duty_account(org_id, company_id)
        igst_id = resolve_gst_account(org_id, tax_code="IGST_INPUT", company_id=company_id)
        payable_id = _resolve_payable_account(org_id, boe.get("vendor_id"))

        if not inventory_id:
            raise ValueError("Import inventory/expense account required")
        if customs > 0 and not customs_id:
            raise ValueError("Customs duty account required")
        if igst > 0 and not igst_id:
            raise ValueError("IGST input account required for import IGST")
        if not payable_id:
            raise ValueError("Payable account required")

        journal_lines: list[dict] = []
        if assessable > 0:
            journal_lines.append(
                {
                    "account_id": inventory_id,
                    "debit_amount": assessable,
                    "credit_amount": 0,
                    "line_description": f"BOE {boe.get('boe_number')} assessable value",
                }
            )
        if customs > 0:
            journal_lines.append(
                {
                    "account_id": customs_id,
                    "debit_amount": customs,
                    "credit_amount": 0,
                    "line_description": f"BOE {boe.get('boe_number')} customs duty",
                }
            )
        if igst > 0:
            journal_lines.append(
                {
                    "account_id": igst_id,
                    "debit_amount": igst,
                    "credit_amount": 0,
                    "line_description": f"BOE {boe.get('boe_number')} import IGST",
                }
            )
        journal_lines.append(
            {
                "account_id": payable_id,
                "debit_amount": 0,
                "credit_amount": total,
                "line_description": f"BOE {boe.get('boe_number')} liability",
            }
        )

        boe_date = str(boe.get("boe_date") or "")[:10]
        journal = journal_service.create_draft(
            org_id,
            created_by=actor_id,
            journal_type="import_customs",
            posting_date=boe_date,
            description=f"Bill of Entry {boe.get('boe_number')}",
            source_type="bill_of_entry",
            source_id=boe_id,
            company_id=company_id,
            currency_code=str(boe.get("currency_code") or "INR"),
            exchange_rate=float(boe.get("exchange_rate") or 1),
            lines=journal_lines,
            idempotency_key=f"boe-post:{boe_id}",
        )
        journal_id = str(journal["journal"]["id"])
        journal_approval_service.approve(
            org_id, journal_id=journal_id, approver_id=actor_id or "system", skip_maker_checker=True
        )
        posting_orchestrator.post_journal(org_id, journal_id=journal_id, posted_by=actor_id or "system")

        updated = bill_of_entry_repository.set_posted(org_id, boe_id=boe_id, journal_id=journal_id)
        if not updated:
            raise ValueError("BOE could not be marked posted — may already be posted")
        return {**self.get_boe(org_id, boe_id=boe_id), "journal_id": journal_id}


bill_of_entry_service = BillOfEntryService()
