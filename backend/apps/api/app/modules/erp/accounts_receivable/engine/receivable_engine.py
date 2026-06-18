from __future__ import annotations

from app.modules.erp.accounts_receivable.engine.account_resolver import resolve_output_gst_account


def build_sales_journal_lines(
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
    """Sales invoice = Receivable Asset Creation: AR Dr + Revenue Cr + Output GST Cr"""
    lines: list[dict] = [
        {
            "account_id": receivable_account_id,
            "debit_amount": total_amount,
            "credit_amount": 0,
            "line_description": "Accounts receivable",
        }
    ]
    if subtotal > 0:
        lines.append({
            "account_id": revenue_account_id,
            "debit_amount": 0,
            "credit_amount": subtotal,
            "line_description": "Sales revenue",
        })
    if gst_lines:
        for gl in gst_lines:
            amount = float(gl.get("amount") or 0)
            if amount <= 0:
                continue
            account_id = gl.get("account_id") or resolve_output_gst_account(
                org_id, tax_code=str(gl.get("tax_code") or "IGST_OUTPUT"), company_id=company_id
            )
            if not account_id:
                raise ValueError(f"Output GST account required for {gl.get('tax_code')}")
            lines.append({
                "account_id": account_id,
                "debit_amount": 0,
                "credit_amount": amount,
                "line_description": gl.get("description") or "Output GST",
                "tax_code": gl.get("tax_code"),
            })
    elif gst_amount > 0:
        gst_account = resolve_output_gst_account(org_id, tax_code="IGST_OUTPUT", company_id=company_id)
        if not gst_account:
            raise ValueError("Output GST account mapping required")
        lines.append({
            "account_id": gst_account,
            "debit_amount": 0,
            "credit_amount": gst_amount,
            "line_description": "Output GST (combined)",
            "tax_code": "IGST_OUTPUT",
        })
    return lines


def build_writeoff_journal_lines(
    *,
    receivable_account_id: str,
    bad_debt_account_id: str,
    amount: float,
) -> list[dict]:
    return [
        {
            "account_id": bad_debt_account_id,
            "debit_amount": amount,
            "credit_amount": 0,
            "line_description": "Bad debt expense",
        },
        {
            "account_id": receivable_account_id,
            "debit_amount": 0,
            "credit_amount": amount,
            "line_description": "Receivable write-off",
        },
    ]
