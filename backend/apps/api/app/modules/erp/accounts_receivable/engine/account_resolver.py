from __future__ import annotations

from app.modules.erp.coa.repositories.account_repository import account_repository
from app.modules.erp.coa.repositories.mapping_repository import mapping_repository

OUTPUT_TAX_TO_GST_TYPE = {
    "CGST_OUTPUT": "cgst_output",
    "SGST_OUTPUT": "sgst_output",
    "IGST_OUTPUT": "igst_output",
}


def resolve_account_by_code(org_id: str, account_code: str) -> str | None:
    for acc in account_repository.list(org_id, limit=2000):
        if str(acc.get("account_code")) == account_code and bool(acc.get("is_active")):
            return str(acc.get("id"))
    return None


def resolve_account_by_type(org_id: str, account_type: str) -> str | None:
    for acc in account_repository.list(org_id, limit=2000):
        if str(acc.get("account_type")) == account_type and bool(acc.get("is_active")):
            return str(acc.get("id"))
    return None


def resolve_output_gst_account(org_id: str, *, tax_code: str, company_id: str | None = None) -> str | None:
    gst_type = OUTPUT_TAX_TO_GST_TYPE.get(str(tax_code or "").strip().upper())
    if not gst_type:
        return None
    mappings = mapping_repository.list_gst_mappings(org_id, company_id=company_id)
    for mapping in mappings:
        if str(mapping.get("gst_type")) == gst_type:
            return str(mapping.get("account_id"))
    return resolve_account_by_type(org_id, "gst_output")


def resolve_receivable_account(org_id: str, customer: dict) -> str | None:
    if customer.get("receivable_account_id"):
        return str(customer["receivable_account_id"])
    return resolve_account_by_type(org_id, "receivable") or resolve_account_by_code(org_id, "1200")


def resolve_revenue_account(org_id: str, customer: dict) -> str | None:
    if customer.get("revenue_account_id"):
        return str(customer["revenue_account_id"])
    return resolve_account_by_type(org_id, "revenue") or resolve_account_by_code(org_id, "4000")


def build_output_gst_lines(
    org_id: str,
    *,
    cgst: float = 0,
    sgst: float = 0,
    igst: float = 0,
    gst_amount: float = 0,
    company_id: str | None = None,
    export_zero_rated: bool = False,
) -> list[dict]:
    if export_zero_rated:
        return []
    lines: list[dict] = []
    for amount, tax_code in ((cgst, "CGST_OUTPUT"), (sgst, "SGST_OUTPUT"), (igst, "IGST_OUTPUT")):
        if amount <= 0:
            continue
        account_id = resolve_output_gst_account(org_id, tax_code=tax_code, company_id=company_id)
        if account_id:
            lines.append({"account_id": account_id, "amount": amount, "tax_code": tax_code})
    if not lines and gst_amount > 0:
        account_id = resolve_output_gst_account(org_id, tax_code="IGST_OUTPUT", company_id=company_id)
        if account_id:
            lines.append({"account_id": account_id, "amount": gst_amount, "tax_code": "IGST_OUTPUT"})
    return lines
