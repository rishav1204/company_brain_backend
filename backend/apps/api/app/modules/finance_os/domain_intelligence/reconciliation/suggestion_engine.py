from __future__ import annotations

from app.modules.erp.query_services import domain_calc


def suggest_matches(
    bank_tx: dict,
    ledger_entries: list[dict],
    *,
    subledger_candidates: list[dict] | None = None,
    rules: list[dict] | None = None,
    limit: int = 5,
) -> list[dict]:
    ranked = domain_calc.rank_all_candidates(
        bank_tx,
        ledger_entries,
        subledger_candidates or [],
        rules=rules,
    )[:limit]
    for item in ranked:
        item["ai_suggestion"] = True
        factors = ", ".join(item.get("factors") or [])
        target = item.get("match_target_type") or "ledger_entry"
        band = item.get("band") or "manual"
        item["explanation"] = f"Match confidence {item.get('confidence_100', item['confidence_score']*100):.0f}% ({band}, {target}) based on {factors}"
    return ranked
