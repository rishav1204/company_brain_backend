from __future__ import annotations

from datetime import date


def aging_days(*, due_date: str, as_of: str | None = None) -> int:
    ref = date.fromisoformat((as_of or date.today().isoformat())[:10])
    due = date.fromisoformat(due_date[:10])
    return (ref - due).days


def aging_bucket(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "1-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    if days_overdue <= 180:
        return "90+"
    if days_overdue <= 365:
        return "180+"
    return "365+"


def bucket_invoice(invoice: dict, *, as_of: str | None = None) -> dict:
    outstanding = float(
        invoice.get("outstanding")
        or (float(invoice.get("total_amount") or 0) - float(invoice.get("paid_amount") or 0))
    )
    days = aging_days(due_date=str(invoice.get("due_date")), as_of=as_of)
    return {**invoice, "outstanding": outstanding, "aging_days": days, "bucket": aging_bucket(days)}
