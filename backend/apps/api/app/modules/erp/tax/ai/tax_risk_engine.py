from __future__ import annotations


def assess_tax_risks(
    *,
    reconciliations: list[dict],
    returns: list[dict],
    calendar: list[dict],
    transactions: list[dict] | None = None,
    tds_transactions: list[dict] | None = None,
    tds_returns: list[dict] | None = None,
    tds_liability: dict | None = None,
    tds_reconciliations: list[dict] | None = None,
) -> dict:
    risks: list[dict] = []
    mismatch_count = sum(1 for r in reconciliations if str(r.get("match_status")) == "mismatch")
    if mismatch_count > 0:
        risks.append({"type": "high_itc_risk", "severity": "high", "detail": f"{mismatch_count} GSTR-2B mismatches open"})
    pending = [c for c in calendar if str(c.get("status")) == "pending"]
    if len(pending) > 3:
        risks.append({"type": "late_filing_risk", "severity": "medium", "detail": f"{len(pending)} compliance obligations pending"})
    unfiled = [r for r in returns if str(r.get("status")) not in {"filed", "approved"}]
    if unfiled:
        risks.append({"type": "unfiled_returns", "severity": "medium", "detail": f"{len(unfiled)} GST returns not filed"})
    txs = transactions or []
    if txs:
        sales_tax = sum(float(t.get("cgst_amount") or 0) + float(t.get("sgst_amount") or 0) + float(t.get("igst_amount") or 0) for t in txs if t.get("gst_type") == "sales")
        purchase_tax = sum(float(t.get("cgst_amount") or 0) + float(t.get("sgst_amount") or 0) + float(t.get("igst_amount") or 0) for t in txs if t.get("gst_type") == "purchase")
        if sales_tax > 0 and purchase_tax > sales_tax * 2:
            risks.append({"type": "abnormal_gst_pattern", "severity": "medium", "detail": "Input GST significantly exceeds output GST"})

    liability = tds_liability or {}
    if float(liability.get("total_liability") or 0) > 0:
        risks.append({
            "type": "tds_liability_pending",
            "severity": "high" if float(liability["total_liability"]) > 100000 else "medium",
            "detail": f"₹{liability['total_liability']:,.2f} TDS pending deposit",
        })
    tds_unfiled = [r for r in (tds_returns or []) if str(r.get("status")) not in {"filed"}]
    if tds_unfiled:
        risks.append({"type": "unfiled_tds_returns", "severity": "medium", "detail": f"{len(tds_unfiled)} TDS returns not filed"})
    for recon in tds_reconciliations or []:
        result = recon.get("result") if isinstance(recon.get("result"), dict) else {}
        mismatches = int((result.get("summary") or {}).get("mismatch_count") or 0)
        if mismatches > 0:
            risks.append({
                "type": "tds_26as_mismatch",
                "severity": "high",
                "detail": f"{mismatches} 26AS reconciliation mismatches",
            })
            break
    unlinked = [t for t in (tds_transactions or []) if str(t.get("status")) == "calculated" and not t.get("challan_id")]
    if len(unlinked) > 5:
        risks.append({"type": "tds_unlinked_challans", "severity": "medium", "detail": f"{len(unlinked)} deductions without challan linkage"})

    return {"risks": risks, "risk_score": min(100, len(risks) * 20)}
