"""Guards against writes to deprecated legacy accounting tables."""

from __future__ import annotations

_LEGACY_BLOCKED_MSG = (
    "Legacy accounting table writes are disabled. "
    "Use ERP modules (erp.ap_invoices, erp.ar_invoices, erp.journals, posting_orchestrator)."
)


def block_legacy_accounting_write(operation: str, *, table: str) -> None:
    raise RuntimeError(f"{_LEGACY_BLOCKED_MSG} Attempted {operation} on {table}.")
