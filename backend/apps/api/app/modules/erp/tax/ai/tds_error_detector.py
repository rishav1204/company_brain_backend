from __future__ import annotations


def detect_tds_errors(
    *,
    transactions: list[dict],
    rules: list[dict] | None = None,
    vendor_pan: str | None = None,
) -> dict:
    flags: list[dict] = []
    rules_by_section = {str(r.get("section_code")): r for r in (rules or [])}

    for tx in transactions:
        section = str(tx.get("section_code") or "")
        rule = rules_by_section.get(section, {})
        rate_pan = float(rule.get("rate_pan") or 0)
        rate_no_pan = float(rule.get("rate_no_pan") or 20)
        gross = float(tx.get("gross_amount") or 0)
        tds = float(tx.get("tds_amount") or 0)
        expected_rate = rate_pan if vendor_pan else max(rate_no_pan, 20)
        if gross > 0 and tds > 0:
            actual_rate = round(tds / gross * 100, 2)
            if abs(actual_rate - expected_rate) > 0.5:
                flags.append({
                    "transaction_id": tx.get("id"),
                    "issue": "wrong_rate",
                    "section_code": section,
                    "expected_rate": expected_rate,
                    "actual_rate": actual_rate,
                })
        if not vendor_pan and tds > 0 and gross > 0 and (tds / gross * 100) < 20:
            flags.append({
                "transaction_id": tx.get("id"),
                "issue": "missing_pan_escalation",
                "section_code": section,
                "detail": "No PAN — rate should be at least 20%",
            })
        if str(tx.get("status")) == "calculated" and not tx.get("challan_id"):
            flags.append({
                "transaction_id": tx.get("id"),
                "issue": "unlinked_challan",
                "section_code": section,
                "tds_amount": tds,
            })

    return {"flags": flags, "flag_count": len(flags)}


def review_vendor_quarter(
    *,
    vendor_id: str,
    quarter: str,
    financial_year: str,
    transactions: list[dict],
    vendor_pan: str | None = None,
    rules: list[dict] | None = None,
) -> dict:
    scoped = [
        t for t in transactions
        if str(t.get("vendor_id") or "") == vendor_id
        and str(t.get("quarter") or "") == quarter
        and str(t.get("financial_year") or "") == financial_year
    ]
    result = detect_tds_errors(transactions=scoped, rules=rules, vendor_pan=vendor_pan)
    return {
        "vendor_id": vendor_id,
        "quarter": quarter,
        "financial_year": financial_year,
        **result,
    }
