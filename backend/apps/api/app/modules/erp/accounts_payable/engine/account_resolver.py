from __future__ import annotations

from app.modules.erp.coa.repositories.account_repository import account_repository
from app.modules.erp.coa.repositories.mapping_repository import mapping_repository

TAX_CODE_TO_GST_TYPE = {
    "CGST_INPUT": "cgst_input",
    "SGST_INPUT": "sgst_input",
    "IGST_INPUT": "igst_input",
    "REVERSE_CHARGE": "reverse_charge",
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


def resolve_gst_account(org_id: str, *, tax_code: str, company_id: str | None = None) -> str | None:
    gst_type = TAX_CODE_TO_GST_TYPE.get(str(tax_code or "").strip().upper())
    if not gst_type:
        return None
    mappings = mapping_repository.list_gst_mappings(org_id, company_id=company_id)
    for mapping in mappings:
        if str(mapping.get("gst_type")) == gst_type:
            return str(mapping.get("account_id"))
    # INT-05: do not silently fall back to a generic GST account; missing mapping must fail fast.
    return None


def build_gst_lines_from_extraction(
    org_id: str,
    extracted_data: dict,
    *,
    company_id: str | None = None,
) -> list[dict]:
    """Build GST debit lines using COA gst_account_mappings."""
    lines: list[dict] = []
    for amount_key, tax_code in (
        ("cgst", "CGST_INPUT"),
        ("sgst", "SGST_INPUT"),
        ("igst", "IGST_INPUT"),
    ):
        amount = float(extracted_data.get(amount_key) or 0)
        if amount <= 0:
            continue
        account_id = resolve_gst_account(org_id, tax_code=tax_code, company_id=company_id)
        if account_id:
            lines.append({
                "account_id": account_id,
                "amount": amount,
                "tax_code": tax_code,
                "description": tax_code,
            })
    gst_total = float(extracted_data.get("gst_amount") or 0)
    if not lines and gst_total > 0:
        account_id = resolve_gst_account(org_id, tax_code="IGST_INPUT", company_id=company_id)
        if account_id:
            lines.append({
                "account_id": account_id,
                "amount": gst_total,
                "tax_code": "IGST_INPUT",
                "description": "Input GST",
            })
    return lines


def resolve_expense_account(org_id: str, extracted_data: dict | None = None) -> str | None:
    if extracted_data:
        from app.modules.platform.documents.ai.ledger_suggester import suggest_ledger_accounts

        for suggestion in suggest_ledger_accounts(extracted_data):
            code = str(suggestion.get("account_code") or "")
            name = str(suggestion.get("account_name") or "").lower()
            if "expense" in name or (code.startswith("5") and "payable" not in name and "gst" not in name):
                account_id = resolve_account_by_code(org_id, code)
                if account_id:
                    return account_id
    return resolve_account_by_type(org_id, "expense") or resolve_account_by_code(org_id, "5000")
