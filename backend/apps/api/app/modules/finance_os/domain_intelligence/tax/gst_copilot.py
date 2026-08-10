from __future__ import annotations


def answer_gst_question(*, question: str, returns: list[dict], transactions: list[dict], itc_summary: dict) -> dict:
    q = question.lower()
    if "liability" in q or "high" in q:
        latest = returns[0] if returns else {}
        payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
        net = payload.get("net_liability") or payload.get("summary", {}).get("total_tax")
        return {
            "answer": f"Net GST liability for latest return period is {net}. Output tax driven by {len([t for t in transactions if t.get('gst_type')=='sales'])} sales transactions.",
            "sources": ["gst_returns", "gst_transactions"],
        }
    if "itc" in q or "credit" in q:
        return {
            "answer": f"ITC available: {itc_summary.get('available', 0)}; claimed: {itc_summary.get('claimed_total', 0)}.",
            "sources": ["itc_ledger"],
        }
    return {"answer": "Review GST transactions and returns for the requested period.", "sources": ["gst_transactions"]}
