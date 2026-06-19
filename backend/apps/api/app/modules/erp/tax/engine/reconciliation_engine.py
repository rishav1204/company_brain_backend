from __future__ import annotations


def match_2b_row(our_tx: dict, gstr2b_row: dict) -> dict:
    score = 0.0
    factors: list[str] = []
    our_ref = str(our_tx.get("metadata", {}).get("invoice_number") or our_tx.get("source_id") or "").lower()
    their_ref = str(gstr2b_row.get("invoice_ref") or "").lower()
    if our_ref and their_ref and (our_ref in their_ref or their_ref in our_ref):
        score += 0.35
        factors.append("invoice_ref")
    our_gstin = str(our_tx.get("party_gstin") or "")
    if our_gstin and our_gstin == str(gstr2b_row.get("vendor_gstin") or ""):
        score += 0.25
        factors.append("vendor_gstin")
    our_tax = float(our_tx.get("cgst_amount") or 0) + float(our_tx.get("sgst_amount") or 0) + float(our_tx.get("igst_amount") or 0)
    their_tax = float(gstr2b_row.get("cgst_amount") or 0) + float(gstr2b_row.get("sgst_amount") or 0) + float(gstr2b_row.get("igst_amount") or 0)
    if their_tax > 0 and abs(our_tax - their_tax) < 1:
        score += 0.4
        factors.append("tax_match")
    elif their_tax > 0 and abs(our_tax - their_tax) / their_tax < 0.02:
        score += 0.25
        factors.append("tax_near")
    status = "matched" if score >= 0.7 else ("mismatch" if score < 0.3 else "partial")
    return {"confidence_score": round(min(1.0, score), 4), "match_status": status, "factors": factors}
