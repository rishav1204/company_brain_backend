from __future__ import annotations

from app.modules.erp.accounts_payable.engine.account_resolver import resolve_gst_account
from app.modules.erp.coa.repositories.account_repository import account_repository


def build_liability_journal_lines(
    org_id: str,
    *,
    expense_account_id: str,
    payable_account_id: str,
    invoice_amount: float,
    gst_amount: float,
    total_amount: float,
    gst_lines: list[dict] | None = None,
    company_id: str | None = None,
) -> list[dict]:
    """
    Invoice = Liability Creation
    Expense Dr + GST Dr + Vendor Payable Cr
    """
    lines: list[dict] = []
    if invoice_amount > 0:
        lines.append({
            "account_id": expense_account_id,
            "debit_amount": invoice_amount,
            "credit_amount": 0,
            "line_description": "Expense",
        })
    if gst_lines:
        for gl in gst_lines:
            amount = float(gl.get("amount") or 0)
            if amount <= 0:
                continue
            account_id = gl.get("account_id") or resolve_gst_account(
                org_id, tax_code=str(gl.get("tax_code") or "IGST_INPUT"), company_id=company_id
            )
            if not account_id:
                raise ValueError(f"GST account required for tax_code {gl.get('tax_code')}")
            lines.append({
                "account_id": account_id,
                "debit_amount": amount,
                "credit_amount": 0,
                "line_description": gl.get("description") or "Input GST",
                "tax_code": gl.get("tax_code"),
            })
    elif gst_amount > 0:
        gst_account = resolve_gst_account(org_id, tax_code="IGST_INPUT", company_id=company_id)
        if not gst_account:
            raise ValueError("GST input account mapping required for invoice with GST")
        lines.append({
            "account_id": gst_account,
            "debit_amount": gst_amount,
            "credit_amount": 0,
            "line_description": "Input GST (combined)",
            "tax_code": "IGST_INPUT",
        })
    lines.append({
        "account_id": payable_account_id,
        "debit_amount": 0,
        "credit_amount": total_amount,
        "line_description": "Vendor payable",
    })
    return lines


def resolve_default_payable_account(org_id: str, vendor: dict) -> str | None:
    if vendor.get("payable_account_id"):
        return str(vendor["payable_account_id"])
    accounts = account_repository.list(org_id, limit=500)
    for acc in accounts:
        if str(acc.get("account_type")) == "payable" and bool(acc.get("is_active")):
            return str(acc.get("id"))
    return None
