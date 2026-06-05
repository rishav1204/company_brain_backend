from __future__ import annotations

from app.modules.erp.coa.repositories.account_repository import account_repository
from app.modules.erp.journals.ai.confidence_engine import score_journal_confidence
from app.modules.platform.documents.ai.ledger_suggester import suggest_ledger_accounts


def _resolve_account_id(org_id: str, account_code: str) -> str | None:
    accounts = account_repository.list(org_id, limit=2000)
    for acc in accounts:
        if str(acc.get("account_code")) == account_code and bool(acc.get("is_active")):
            return str(acc.get("id"))
    return None


def build_draft_lines_from_extraction(org_id: str, extracted_data: dict) -> tuple[list[dict], dict]:
    """
    Build balanced draft journal lines from invoice extraction.
    Suggestion-only — never posts.
    """
    subtotal = float(extracted_data.get("subtotal") or extracted_data.get("amount") or 0)
    cgst = float(extracted_data.get("cgst") or 0)
    sgst = float(extracted_data.get("sgst") or 0)
    igst = float(extracted_data.get("igst") or 0)
    total = float(extracted_data.get("total_amount") or extracted_data.get("total") or (subtotal + cgst + sgst + igst))
    if total <= 0:
        return [], score_journal_confidence(ledger_confidence=0, gst_confidence=0, vendor_confidence=0)

    suggestions = suggest_ledger_accounts(extracted_data)
    expense_code = "5000"
    payable_code = "2100"
    if suggestions:
        for s in suggestions:
            code = str(s.get("account_code") or "")
            name = str(s.get("account_name") or "").lower()
            if "payable" in name:
                payable_code = code
            elif "expense" in name or "gst" not in name:
                expense_code = code

    lines: list[dict] = []
    expense_id = _resolve_account_id(org_id, expense_code)
    payable_id = _resolve_account_id(org_id, payable_code)
    if expense_id and subtotal > 0:
        lines.append(
            {
                "account_id": expense_id,
                "debit_amount": subtotal,
                "credit_amount": 0,
                "line_description": "Expense (AI suggested)",
            }
        )
    for tax_amount, tax_code in ((cgst, "CGST_INPUT"), (sgst, "SGST_INPUT"), (igst, "IGST_INPUT")):
        if tax_amount <= 0:
            continue
        tax_account = _resolve_account_id(org_id, "2100")
        if tax_account:
            lines.append(
                {
                    "account_id": tax_account,
                    "debit_amount": tax_amount,
                    "credit_amount": 0,
                    "line_description": f"{tax_code} (AI suggested)",
                    "tax_code": tax_code,
                }
            )
    if payable_id:
        lines.append(
            {
                "account_id": payable_id,
                "debit_amount": 0,
                "credit_amount": total,
                "line_description": "Vendor payable (AI suggested)",
            }
        )

    confidence = score_journal_confidence(
        ledger_confidence=0.94 if expense_id and payable_id else 0.55,
        gst_confidence=0.99 if (cgst + sgst + igst) >= 0 else 0.7,
        vendor_confidence=0.97 if extracted_data.get("vendor_name") else 0.6,
    )
    return lines, confidence
