from __future__ import annotations


def answer_treasury_question(*, question: str, position: dict, liquidity: dict) -> dict:
    q = question.lower().strip()
    net = float(position.get("net_liquidity") or 0)
    upcoming = float(position.get("upcoming_payments") or 0)
    available = float(position.get("available_cash") or 0)
    band = liquidity.get("health_band", "healthy")

    if "shortage" in q or "run out" in q or "next month" in q:
        risk = liquidity.get("risk_level", "low")
        shortage = liquidity.get("shortage_buckets") or []
        fc = liquidity.get("forecast_30d") or {}
        answer = (
            f"Liquidity risk is {risk} (health band: {band}). "
            f"30-day forecast balance: {fc.get('forecast_cash_balance', 'n/a')}. "
            f"Net liquidity is {net:,.2f}. "
            + (f"Potential shortage in horizons: {', '.join(shortage)}." if shortage else "No shortage projected in standard horizons.")
        )
    elif "pressure" in q or "causing" in q:
        risks = liquidity.get("risks") or []
        causes = "; ".join(r.get("message", "") for r in risks[:3]) or "Upcoming AP and compliance obligations"
        answer = f"Liquidity pressure causes: {causes}. Coverage: {liquidity.get('liquidity_coverage')}, band: {band}."
    elif "pay all vendors" in q or "pay everyone" in q:
        can_pay = available >= upcoming
        answer = (
            f"Available cash {available:,.2f} vs upcoming payments {upcoming:,.2f}. "
            + ("You can cover scheduled vendor payments this week." if can_pay else "Insufficient cash for all scheduled vendor payments.")
        )
    else:
        answer = (
            f"Current available cash {available:,.2f}, expected collections {position.get('expected_collections', 0):,.2f}, "
            f"upcoming payments {upcoming:,.2f}, net liquidity {net:,.2f}, health band {band}."
        )
    from app.modules.erp.treasury.ai.treasury_advisor import advise_treasury

    return {
        "question": question,
        "answer": answer,
        "advisory_only": True,
        "suggestions": advise_treasury(liquidity=liquidity, position=position),
        "position": position,
    }
