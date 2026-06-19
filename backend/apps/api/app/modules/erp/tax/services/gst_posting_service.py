from __future__ import annotations

from app.modules.erp.accounts_payable.engine.account_resolver import resolve_gst_account
from app.modules.erp.accounts_payable.engine.account_resolver import resolve_account_by_type
from app.modules.erp.accounts_payable.engine.payable_engine import build_liability_journal_lines
from app.modules.erp.accounts_receivable.engine.receivable_engine import build_sales_journal_lines


def build_purchase_journal_lines(
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
    """Standard AP purchase: Expense Dr + Input GST Dr + Vendor Payable Cr."""
    return build_liability_journal_lines(
        org_id,
        expense_account_id=expense_account_id,
        payable_account_id=payable_account_id,
        invoice_amount=invoice_amount,
        gst_amount=gst_amount,
        total_amount=total_amount,
        gst_lines=gst_lines,
        company_id=company_id,
    )


def build_sale_journal_lines(
    org_id: str,
    *,
    receivable_account_id: str,
    revenue_account_id: str,
    subtotal: float,
    gst_amount: float,
    total_amount: float,
    gst_lines: list[dict] | None = None,
    company_id: str | None = None,
) -> list[dict]:
    """Standard AR sale: Customer Dr + Revenue Cr + Output GST Cr."""
    return build_sales_journal_lines(
        org_id,
        receivable_account_id=receivable_account_id,
        revenue_account_id=revenue_account_id,
        subtotal=subtotal,
        gst_amount=gst_amount,
        total_amount=total_amount,
        gst_lines=gst_lines,
        company_id=company_id,
    )


def build_rcm_journal_lines(
    org_id: str,
    *,
    expense_account_id: str,
    payable_account_id: str,
    invoice_amount: float,
    gst_lines: list[dict] | None = None,
    gst_amount: float = 0,
    company_id: str | None = None,
) -> list[dict]:
    """
    Reverse charge: Expense Dr + Input GST Dr + RCM Payable Cr + Vendor Cr (taxable only).
    Recipient self-assesses GST; vendor invoice excludes tax.
    """
    rcm_account_id = resolve_account_by_type(org_id, "reverse_charge")
    if not rcm_account_id:
        rcm_account_id = resolve_gst_account(org_id, tax_code="REVERSE_CHARGE", company_id=company_id)
    if not rcm_account_id:
        raise ValueError("RCM payable account required for reverse charge invoice")

    lines: list[dict] = []
    if invoice_amount > 0:
        lines.append({
            "account_id": expense_account_id,
            "debit_amount": invoice_amount,
            "credit_amount": 0,
            "line_description": "Expense (RCM)",
        })

    total_gst = 0.0
    if gst_lines:
        for gl in gst_lines:
            amount = float(gl.get("amount") or 0)
            if amount <= 0:
                continue
            account_id = gl.get("account_id") or resolve_gst_account(
                org_id, tax_code=str(gl.get("tax_code") or "IGST_INPUT"), company_id=company_id
            )
            if not account_id:
                raise ValueError(f"GST input account required for RCM tax_code {gl.get('tax_code')}")
            lines.append({
                "account_id": account_id,
                "debit_amount": amount,
                "credit_amount": 0,
                "line_description": gl.get("description") or "Input GST (RCM)",
                "tax_code": gl.get("tax_code"),
            })
            total_gst += amount
    elif gst_amount > 0:
        gst_account = resolve_gst_account(org_id, tax_code="IGST_INPUT", company_id=company_id)
        if not gst_account:
            raise ValueError("GST input account mapping required for RCM invoice")
        lines.append({
            "account_id": gst_account,
            "debit_amount": gst_amount,
            "credit_amount": 0,
            "line_description": "Input GST (RCM combined)",
            "tax_code": "IGST_INPUT",
        })
        total_gst = gst_amount

    if total_gst > 0:
        lines.append({
            "account_id": rcm_account_id,
            "debit_amount": 0,
            "credit_amount": total_gst,
            "line_description": "RCM tax liability",
            "tax_code": "REVERSE_CHARGE",
        })

    lines.append({
        "account_id": payable_account_id,
        "debit_amount": 0,
        "credit_amount": invoice_amount,
        "line_description": "Vendor payable (RCM taxable)",
    })
    return lines
