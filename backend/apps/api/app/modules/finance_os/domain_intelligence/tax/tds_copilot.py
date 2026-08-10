from __future__ import annotations


def answer_tds_question(
    *,
    question: str,
    liability: dict | None = None,
    transactions: list[dict] | None = None,
    returns: list[dict] | None = None,
    challans: list[dict] | None = None,
) -> dict:
    q = question.lower()
    liability = liability or {}
    txs = transactions or []
    returns = returns or []
    challans = challans or []

    if "liability" in q or "pending" in q:
        total = liability.get("total_liability", 0)
        return {
            "answer": f"Pending TDS liability is ₹{total:,.2f} across {liability.get('transaction_count', 0)} deductions.",
            "sources": ["tds_liability"],
        }
    if "challan" in q:
        pending = [c for c in challans if str(c.get("status")) == "pending"]
        return {
            "answer": f"{len(pending)} challan(s) pending deposit. Total pending amount ₹{sum(float(c.get('amount') or 0) for c in pending):,.2f}.",
            "sources": ["tds_challans"],
        }
    if "26q" in q or "return" in q:
        unfiled = [r for r in returns if str(r.get("status")) not in {"filed"}]
        return {
            "answer": f"{len(unfiled)} TDS return(s) not yet filed. Latest period: {returns[0].get('return_period') if returns else 'N/A'}.",
            "sources": ["tds_returns"],
        }
    if "form 16" in q or "form16" in q:
        vendors = len({str(t.get('vendor_id')) for t in txs if t.get('vendor_id')})
        return {
            "answer": f"{vendors} vendor(s) have TDS deductions on record — Form 16A can be generated per vendor/quarter.",
            "sources": ["tds_transactions"],
        }
    return {
        "answer": "Review TDS liability, challans, and quarterly returns for the requested period.",
        "sources": ["tds_transactions", "tds_returns"],
    }
