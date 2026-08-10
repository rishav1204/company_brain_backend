from __future__ import annotations


def detect_journal_anomalies(lines: list[dict], *, historical_avg: float | None = None) -> list[dict]:
    """Lightweight anomaly hints for finance review (never auto-posts)."""
    anomalies: list[dict] = []
    total_debit = sum(float(l.get("debit_amount") or 0) for l in lines)
    if total_debit <= 0:
        anomalies.append({"code": "zero_total", "severity": "high", "message": "Journal total is zero"})
    if historical_avg and total_debit > historical_avg * 3:
        anomalies.append(
            {
                "code": "amount_spike",
                "severity": "medium",
                "message": f"Total {total_debit} exceeds 3x historical average {historical_avg}",
            }
        )
    account_ids = [str(l.get("account_id")) for l in lines if l.get("account_id")]
    if len(account_ids) != len(set(account_ids)) and len(account_ids) > 2:
        anomalies.append({"code": "duplicate_accounts", "severity": "low", "message": "Duplicate accounts on multiple lines"})
    return anomalies
