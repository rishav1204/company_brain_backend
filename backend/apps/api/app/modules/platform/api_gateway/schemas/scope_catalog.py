from __future__ import annotations

"""Partner API scope catalog — maps to M34 actions."""

SCOPE_CATALOG: dict[str, str] = {
    "invoice.read": "invoice.read",
    "invoice.write": "invoice.write",
    "payments.read": "payments.read",
    "payments.write": "payments.write",
    "reports.read": "reports.read",
    "webhooks.manage": "webhook.subscribe",
    "integrations.sync": "integrations.sync",
    "api.keys.manage": "api.key.create",
    "admin": "admin",
}

PARTNER_SUBSCRIBABLE_EVENTS: frozenset[str] = frozenset(
    {
        "invoice.created",
        "erp.invoice.created",
        "erp.invoice.approved",
        "invoice.approved",
        "invoice.paid",
        "sales.invoice.created",
        "customer_invoice.created",
        "customer.payment.received",
        "payment.received",
        "payment.executed",
        "bank.transaction.imported",
        "bank.feed.imported",
        "bank.statement.imported",
        "erp.gst.return.generated",
        "gst.return.generated",
        "gst.return.filed",
        "workflow.started",
        "workflow.completed",
        "workflow.rejected",
        "approval.rejected",
        "agent.completed",
        "forecast.generated",
        "webhook.delivered",
        "webhook.failed",
        "consolidation.completed",
    }
)

EVENT_ALIASES: dict[str, str] = {
    "invoice.approved": "erp.invoice.approved",
    "invoice.paid": "erp.payment.completed",
    "customer_invoice.created": "sales.invoice.created",
    "gst.return.generated": "erp.gst.return.generated",
    "gst.return.filed": "erp.gst.return.generated",
    "workflow.rejected": "approval.rejected",
    "bank.transaction.imported": "bank.feed.imported",
}


def normalize_event_type(event_type: str) -> str:
    return EVENT_ALIASES.get(event_type, event_type)


def scope_to_action(scope: str) -> str:
    return SCOPE_CATALOG.get(scope, scope)
