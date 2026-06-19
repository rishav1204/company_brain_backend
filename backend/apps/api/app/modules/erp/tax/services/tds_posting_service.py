from __future__ import annotations

from app.modules.erp.accounts_payable.engine.account_resolver import resolve_account_by_type


def resolve_tds_payable_account(org_id: str) -> str | None:
    return resolve_account_by_type(org_id, "tds_payable")


def resolve_tcs_payable_account(org_id: str) -> str | None:
    return resolve_account_by_type(org_id, "tcs_payable")


def build_payment_journal_lines(
    *,
    payable_account_id: str,
    bank_account_id: str,
    tds_payable_account_id: str | None,
    gross_amount: float,
    tds_amount: float,
    net_amount: float,
) -> list[dict]:
    """Payment with TDS: Payable Dr gross, Bank Cr net, TDS Payable Cr tds."""
    lines = [
        {
            "account_id": payable_account_id,
            "debit_amount": gross_amount,
            "credit_amount": 0,
            "line_description": "Vendor payable settlement",
        },
        {
            "account_id": bank_account_id,
            "debit_amount": 0,
            "credit_amount": net_amount,
            "line_description": "Bank payment (net of TDS)",
        },
    ]
    if tds_amount > 0:
        if not tds_payable_account_id:
            raise ValueError("TDS payable account required when TDS is deducted")
        lines.append({
            "account_id": tds_payable_account_id,
            "debit_amount": 0,
            "credit_amount": tds_amount,
            "line_description": "TDS payable",
        })
    return lines


def build_payment_journal_lines_no_tds(*, payable_account_id: str, bank_account_id: str, amount: float) -> list[dict]:
    return build_payment_journal_lines(
        payable_account_id=payable_account_id,
        bank_account_id=bank_account_id,
        tds_payable_account_id=None,
        gross_amount=amount,
        tds_amount=0,
        net_amount=amount,
    )


def build_sale_journal_lines_with_tcs(
    *,
    receivable_account_id: str,
    revenue_account_id: str,
    tcs_payable_account_id: str | None,
    gross_amount: float,
    tcs_amount: float,
    total_collected: float,
) -> list[dict]:
    """TCS on sale: Customer Dr total, Revenue Cr gross, TCS Payable Cr tcs."""
    lines = [
        {
            "account_id": receivable_account_id,
            "debit_amount": total_collected,
            "credit_amount": 0,
            "line_description": "Customer receivable (incl TCS)",
        },
        {
            "account_id": revenue_account_id,
            "debit_amount": 0,
            "credit_amount": gross_amount,
            "line_description": "Revenue",
        },
    ]
    if tcs_amount > 0:
        if not tcs_payable_account_id:
            raise ValueError("TCS payable account required when TCS is collected")
        lines.append({
            "account_id": tcs_payable_account_id,
            "debit_amount": 0,
            "credit_amount": tcs_amount,
            "line_description": "TCS payable",
        })
    return lines
