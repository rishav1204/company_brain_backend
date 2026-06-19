from __future__ import annotations


def vendor_mismatch_report(reconciliations: list[dict]) -> dict:
    vendors: dict[str, int] = {}
    for r in reconciliations:
        if str(r.get("match_status")) not in {"mismatch", "partial"}:
            continue
        meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
        vendor = str(meta.get("vendor_gstin") or "unknown")
        vendors[vendor] = vendors.get(vendor, 0) + 1
    ranked = sorted(vendors.items(), key=lambda x: x[1], reverse=True)
    return {
        "vendors": [{"vendor_gstin": v, "mismatch_count": c} for v, c in ranked[:10]],
        "summary": f"{len(ranked)} vendors with ITC mismatches",
    }


def answer_compliance_question(*, question: str, reconciliations: list[dict]) -> dict:
    q = question.lower()
    if "vendor" in q and "mismatch" in q:
        report = vendor_mismatch_report(reconciliations)
        top = report["vendors"][:3]
        names = ", ".join(v["vendor_gstin"] for v in top) or "none"
        return {"answer": f"Top vendors causing ITC mismatches: {names}.", "report": report}
    return {"answer": "Run GSTR-2B reconciliation to identify vendor-level mismatches.", "report": {}}
