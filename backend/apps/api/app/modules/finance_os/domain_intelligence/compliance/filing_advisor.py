from __future__ import annotations


def filing_readiness_score(
    *,
    gst_returns: list[dict] | None = None,
    tds_returns: list[dict] | None = None,
    tds_liability: dict | None = None,
    reconciliations: list[dict] | None = None,
    obligations: list[dict] | None = None,
) -> dict:
    weights = {
        "gst_return_prepared": 25,
        "gstr2b_reconciled": 25,
        "tds_liability_deposited": 25,
        "workflow_approved": 25,
    }
    scores = {k: 0 for k in weights}
    gst_returns = gst_returns or []
    if any(str(r.get("status")) in {"generated", "filed", "submitted"} for r in gst_returns):
        scores["gst_return_prepared"] = weights["gst_return_prepared"]
    reconciliations = reconciliations or []
    if reconciliations and all(str(r.get("match_status")) == "matched" for r in reconciliations[:5]):
        scores["gstr2b_reconciled"] = weights["gstr2b_reconciled"]
    elif reconciliations and any(str(r.get("match_status")) == "matched" for r in reconciliations):
        scores["gstr2b_reconciled"] = weights["gstr2b_reconciled"] // 2
    liability = float((tds_liability or {}).get("total_liability") or 0)
    if liability <= 0:
        scores["tds_liability_deposited"] = weights["tds_liability_deposited"]
    elif liability < 1000:
        scores["tds_liability_deposited"] = weights["tds_liability_deposited"] // 2
    obligations = obligations or []
    open_critical = [o for o in obligations if o.get("status") == "overdue" and o.get("priority") == "critical"]
    if not open_critical:
        scores["workflow_approved"] = weights["workflow_approved"]
    total = sum(scores.values())
    return {"score": total, "components": scores, "max_score": sum(weights.values())}
