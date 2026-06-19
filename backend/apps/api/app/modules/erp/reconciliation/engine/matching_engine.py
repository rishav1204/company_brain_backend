from __future__ import annotations

from datetime import date

from app.modules.erp.reconciliation.engine.confidence_engine import compute_confidence, load_weights
from app.modules.erp.reconciliation.engine.fuzzy_matching_engine import counterparty_fuzzy, narration_similarity


def score_match(
    *,
    bank_amount: float,
    bank_date: str,
    bank_reference: str,
    bank_description: str,
    bank_counterparty: str,
    ledger_debit: float,
    ledger_credit: float,
    ledger_date: str,
    ledger_reference: str,
    ledger_counterparty: str = "",
    source_type: str | None = None,
    source_id: str | None = None,
    candidate_id: str | None = None,
    rules: list[dict] | None = None,
) -> dict:
    weights = load_weights(rules)
    factors: dict[str, bool] = {}

    if source_id and candidate_id and str(source_id) == str(candidate_id):
        factors["source_id_match"] = True
        scored = compute_confidence(factors, weights)
        scored["match_type"] = "suggested"
        return scored

    ledger_amount = max(float(ledger_debit or 0), float(ledger_credit or 0))
    if ledger_amount > 0 and abs(bank_amount - ledger_amount) < 0.05:
        factors["amount_exact"] = True
    elif ledger_amount > 0 and abs(bank_amount - ledger_amount) / ledger_amount < 0.02:
        factors["amount_near"] = True

    try:
        bd = date.fromisoformat(str(bank_date)[:10])
        ld = date.fromisoformat(str(ledger_date)[:10])
        delta = abs((bd - ld).days)
        if delta == 0:
            factors["date_exact"] = True
        elif delta <= 3:
            factors["date_close"] = True
        elif delta <= 7:
            factors["date_week"] = True
    except ValueError:
        pass

    ref = (bank_reference or "").strip().lower()
    lref = (ledger_reference or "").strip().lower()
    narr = (bank_description or "").lower()
    if ref and lref and (ref in lref or lref in ref or ref in narr):
        factors["reference_match"] = True

    if narration_similarity(bank_description, ledger_reference) >= 0.6:
        factors["narration_fuzzy"] = True

    lcp = (ledger_counterparty or "").lower()
    cp = (bank_counterparty or "").lower()
    if cp and (counterparty_fuzzy(bank_description, cp) >= 0.5 or cp in lcp or cp in narr):
        factors["counterparty_match"] = True

    scored = compute_confidence(factors, weights)
    scored["match_type"] = "exception" if scored["confidence_score"] < 0.3 else "suggested"
    return scored


def rank_candidates(bank_tx: dict, ledger_entries: list[dict], *, rules: list[dict] | None = None) -> list[dict]:
    bank_amount = float(bank_tx.get("amount") or 0)
    results = []
    for entry in ledger_entries:
        debit = float(entry.get("debit_amount") or 0)
        credit = float(entry.get("credit_amount") or 0)
        if max(debit, credit) <= 0:
            continue
        scored = score_match(
            bank_amount=bank_amount,
            bank_date=str(bank_tx.get("transaction_date") or ""),
            bank_reference=str(bank_tx.get("transaction_reference") or ""),
            bank_description=str(bank_tx.get("description") or ""),
            bank_counterparty=str(bank_tx.get("counterparty_ref") or ""),
            ledger_debit=debit,
            ledger_credit=credit,
            ledger_date=str(entry.get("posting_date") or ""),
            ledger_reference=str(entry.get("reference_id") or entry.get("id") or ""),
            rules=rules,
        )
        results.append({
            **scored,
            "ledger_entry_id": entry.get("id"),
            "match_target_type": "ledger_entry",
            "match_target_id": entry.get("id"),
            "ledger_entry": entry,
        })
    results.sort(key=lambda x: x["confidence_score"], reverse=True)
    return results


def rank_subledger_candidates(bank_tx: dict, candidates: list[dict], *, rules: list[dict] | None = None) -> list[dict]:
    bank_amount = float(bank_tx.get("amount") or 0)
    tx_type = str(bank_tx.get("transaction_type") or "").lower()
    source_id = bank_tx.get("source_id")
    source_type = str(bank_tx.get("source_type") or "")
    results = []
    for cand in candidates:
        cand_type = str(cand.get("target_type") or "")
        amount = float(cand.get("amount") or 0)
        if amount <= 0:
            continue
        if tx_type == "credit" and cand_type in {"ap_payment", "ap_invoice"}:
            continue
        if tx_type == "debit" and cand_type in {"ar_receipt", "ar_invoice"}:
            continue
        cand_id = str(cand.get("id") or "")
        scored = score_match(
            bank_amount=bank_amount,
            bank_date=str(bank_tx.get("transaction_date") or ""),
            bank_reference=str(bank_tx.get("transaction_reference") or ""),
            bank_description=str(bank_tx.get("description") or ""),
            bank_counterparty=str(bank_tx.get("counterparty_ref") or ""),
            ledger_debit=amount if cand_type in {"ap_payment", "ap_invoice"} else 0,
            ledger_credit=amount if cand_type in {"ar_receipt", "ar_invoice"} else amount,
            ledger_date=str(cand.get("date") or ""),
            ledger_reference=str(cand.get("reference") or cand_id),
            ledger_counterparty=str(cand.get("counterparty_name") or cand.get("counterparty_ref") or ""),
            source_type=source_type,
            source_id=str(source_id) if source_id else None,
            candidate_id=cand_id,
            rules=rules,
        )
        results.append({
            **scored,
            "ledger_entry_id": cand.get("ledger_entry_id"),
            "match_target_type": cand_type,
            "match_target_id": cand_id,
            "subledger": cand,
        })
    results.sort(key=lambda x: x["confidence_score"], reverse=True)
    return results


def rank_all_candidates(
    bank_tx: dict,
    ledger_entries: list[dict],
    subledger_candidates: list[dict],
    *,
    rules: list[dict] | None = None,
) -> list[dict]:
    combined = rank_candidates(bank_tx, ledger_entries, rules=rules) + rank_subledger_candidates(
        bank_tx, subledger_candidates, rules=rules
    )
    combined.sort(key=lambda x: x["confidence_score"], reverse=True)
    return combined
