from __future__ import annotations

from app.modules.platform.events.services.event_service import platform_event_service


def emit_bank_statement_imported(
    org_id: str,
    *,
    statement_id: str,
    account_id: str | None = None,
    trace_id: str | None = None,
) -> dict:
    return platform_event_service.publish(
        event_type="bank.statement.imported",
        org_id=org_id,
        source="integration.bank",
        entity_type="bank_statement",
        entity_id=statement_id,
        payload={"statement_id": statement_id, "account_id": account_id},
        trace_id=trace_id,
    )
