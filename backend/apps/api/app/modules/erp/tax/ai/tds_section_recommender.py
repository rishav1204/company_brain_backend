from __future__ import annotations


def recommend_section(
    *,
    payment_type: str | None = None,
    expense_category: str | None = None,
    vendor_metadata: dict | None = None,
    amount: float = 0,
    rules: list[dict] | None = None,
) -> dict:
    vendor_meta = vendor_metadata or {}
    if vendor_meta.get("tds_section"):
        return {
            "section_code": str(vendor_meta["tds_section"]),
            "confidence": 0.95,
            "reason": "Vendor master override",
        }

    ptype = str(payment_type or vendor_meta.get("payment_type") or vendor_meta.get("vendor_type") or "").lower()
    category = str(expense_category or vendor_meta.get("expense_category") or "").lower()

    for rule in rules or []:
        if ptype and str(rule.get("payment_type") or "").lower() == ptype:
            return {
                "section_code": rule["section_code"],
                "confidence": 0.85,
                "reason": f"Payment type match: {ptype}",
            }
        if category and str(rule.get("expense_category") or "").lower() == category:
            return {
                "section_code": rule["section_code"],
                "confidence": 0.8,
                "reason": f"Expense category match: {category}",
            }

    defaults = {
        "professional": "194J",
        "contract": "194C",
        "contractor": "194C",
        "commission": "194H",
        "rent": "194I",
        "goods": "194Q",
        "interest": "194A",
    }
    if ptype in defaults:
        return {"section_code": defaults[ptype], "confidence": 0.7, "reason": f"Default map for {ptype}"}

    if amount >= 5_000_000:
        return {"section_code": "194Q", "confidence": 0.55, "reason": "High value — consider 194Q goods purchase"}
    return {"section_code": "194C", "confidence": 0.5, "reason": "Default contractor section"}
