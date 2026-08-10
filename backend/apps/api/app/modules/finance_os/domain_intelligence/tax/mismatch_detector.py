from __future__ import annotations


def detect_mismatches(our_tx: dict, gstr2b_row: dict) -> dict:
    flags: list[str] = []
    our_tax = float(our_tx.get("cgst_amount") or 0) + float(our_tx.get("sgst_amount") or 0) + float(our_tx.get("igst_amount") or 0)
    their_tax = float(gstr2b_row.get("cgst_amount") or 0) + float(gstr2b_row.get("sgst_amount") or 0) + float(gstr2b_row.get("igst_amount") or 0)
    tax_delta = round(abs(our_tax - their_tax), 2)
    if tax_delta > 1:
        flags.append("gst_difference")
    if not our_tx.get("party_gstin"):
        flags.append("missing_vendor_gstin")
    if their_tax > 0 and our_tax == 0:
        flags.append("missing_invoice")
    if tax_delta > 10000:
        flags.append("itc_risk")
    vendor_gstin = str(gstr2b_row.get("vendor_gstin") or our_tx.get("party_gstin") or "")
    if vendor_gstin and their_tax > 0 and tax_delta > 500:
        flags.append("vendor_filing_issue")
    if gstr2b_row.get("metadata", {}).get("vendor_non_filer"):
        flags.append("vendor_non_compliance")
    return {"flags": flags, "tax_delta": tax_delta, "high_risk": "itc_risk" in flags or "vendor_filing_issue" in flags}
