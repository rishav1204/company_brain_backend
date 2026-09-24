from __future__ import annotations

from app.modules.platform.regulatory.services.regulatory_resolver import (
    RegulatoryConfigError,
    regulatory_resolver,
)


def recommend_section(
    *,
    payment_type: str | None = None,
    expense_category: str | None = None,
    vendor_metadata: dict | None = None,
    amount: float = 0,
    rules: list[dict] | None = None,
    org_id: str | None = None,
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

    # Prefer platform TDS templates payment_type mapping when rules empty
    try:
        from app.modules.platform.regulatory.repositories.regulatory_repository import (
            regulatory_repository,
        )

        for tmpl in regulatory_repository.list_tds_templates():
            tpay = str(tmpl.get("payment_type") or "").lower()
            if ptype and tpay == ptype:
                return {
                    "section_code": tmpl["section_code"],
                    "confidence": 0.7,
                    "reason": f"Template map for {ptype}",
                }
        try:
            hint = regulatory_resolver.resolve_threshold_amount(
                "tds.194q_amount_hint", org_id=org_id, required=False, default=None
            )
        except RegulatoryConfigError:
            hint = None
        if hint is not None and amount >= float(hint):
            return {
                "section_code": "194Q",
                "confidence": 0.55,
                "reason": "High value — consider 194Q goods purchase",
            }
        # Default first contractor template
        for tmpl in regulatory_repository.list_tds_templates():
            if tmpl.get("section_code") == "194C":
                return {
                    "section_code": "194C",
                    "confidence": 0.5,
                    "reason": "Default contractor section from template",
                }
    except Exception:
        pass

    return {
        "section_code": "194C",
        "confidence": 0.4,
        "reason": "Fallback when regulatory templates unavailable",
    }
