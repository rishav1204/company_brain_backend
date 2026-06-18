from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventDefinition:
    event_type: str
    owner: str
    category: str
    version: str = "v1"


ERP_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("erp.invoice.created", "erp.ap", "domain"),
    EventDefinition("erp.invoice.approved", "erp.ap", "domain"),
    EventDefinition("erp.invoice.updated", "erp.ap", "domain"),
    EventDefinition("erp.payment.completed", "erp.treasury", "domain"),
    EventDefinition("erp.payment.failed", "erp.treasury", "domain"),
    EventDefinition("erp.journal.created", "erp.journals", "domain"),
    EventDefinition("erp.journal.approved", "erp.journals", "domain"),
    EventDefinition("erp.journal.posted", "erp.journals", "domain"),
    EventDefinition("erp.journal.reversed", "erp.journals", "domain"),
    EventDefinition("journal.created", "erp.journals", "domain"),
    EventDefinition("journal.approved", "erp.journals", "domain"),
    EventDefinition("journal.reversed", "erp.journals", "domain"),
    EventDefinition("erp.ledger.posted", "erp.gl", "domain"),
    EventDefinition("erp.ledger.reversed", "erp.gl", "domain"),
    EventDefinition("erp.fiscal_period.locked", "erp.gl", "domain"),
    EventDefinition("erp.fiscal_period.closed", "erp.gl", "domain"),
    EventDefinition("erp.trial_balance.generated", "erp.gl", "domain"),
    EventDefinition("erp.account.created", "erp.coa", "domain"),
    EventDefinition("erp.account.updated", "erp.coa", "domain"),
    EventDefinition("erp.gst.mapping.updated", "erp.coa", "domain"),
    EventDefinition("erp.vendor.created", "erp.ap", "domain"),
    EventDefinition("erp.gst.return.generated", "erp.gst", "domain"),
    EventDefinition("erp.reconciliation.pending", "erp.reconciliation", "domain"),
    EventDefinition("invoice.created", "erp.ap", "domain"),
    EventDefinition("invoice.due", "erp.ap", "domain"),
    EventDefinition("invoice.received", "erp.ap", "domain"),
    EventDefinition("payment.scheduled", "erp.ap", "domain"),
    EventDefinition("payment.completed", "erp.treasury", "domain"),
    EventDefinition("sales.invoice.created", "erp.ar", "domain"),
    EventDefinition("invoice.issued", "erp.ar", "domain"),
    EventDefinition("invoice.overdue", "erp.ar", "domain"),
    EventDefinition("collection.required", "erp.ar", "domain"),
    EventDefinition("payment.received", "erp.ar", "domain"),
    EventDefinition("customer.payment.received", "erp.ar", "domain"),
    EventDefinition("customer.credit.limit.exceeded", "erp.ar", "domain"),
    EventDefinition("journal.posted", "erp.journals", "domain"),
    EventDefinition("erp.journal.posting.completed", "erp.journals", "domain"),
    EventDefinition("ledger.posted", "erp.gl", "domain"),
)

WORKFLOW_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("workflow.approved", "workflow.engine", "domain"),
    EventDefinition("workflow.created", "workflow.engine", "domain"),
    EventDefinition("workflow.started", "workflow.engine", "domain"),
    EventDefinition("workflow.completed", "workflow.engine", "domain"),
    EventDefinition("workflow.failed", "workflow.engine", "domain"),
    EventDefinition("workflow.updated", "workflow.engine", "domain"),
    EventDefinition("workflow.advance.requested", "workflow.engine", "domain"),
    EventDefinition("workflow.escalated", "workflow.engine", "domain"),
    EventDefinition("workflow.retry.scheduled", "workflow.engine", "domain"),
    EventDefinition("workflow.step.completed", "workflow.engine", "domain"),
    EventDefinition("workflow.step.system_task", "workflow.engine", "domain"),
    EventDefinition("approval.requested", "workflow.engine", "domain"),
    EventDefinition("approval.completed", "workflow.engine", "domain"),
    EventDefinition("approval.rejected", "workflow.engine", "domain"),
    EventDefinition("sla.breached", "workflow.engine", "domain"),
)

AI_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("invoice.ai.reviewed", "ai.runtime", "ai"),
    EventDefinition("payment.risk.detected", "ai.runtime", "ai"),
    EventDefinition("reconciliation.match.suggested", "ai.reconciliation", "ai"),
    EventDefinition("risk.detected", "ai.runtime", "ai"),
    EventDefinition("agent.run.requested", "ai.runtime", "ai"),
    EventDefinition("ai.ocr.requested", "ai.runtime", "ai"),
)

INTEGRATION_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("bank.statement.imported", "integration.bank", "integration"),
    EventDefinition("gst.response.received", "integration.gst", "integration"),
    EventDefinition("webhook.received", "integration.webhooks", "integration"),
)

SCHEDULER_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("scheduler.tick", "platform.scheduler", "system"),
    EventDefinition("scheduler.sla.scan", "platform.scheduler", "system"),
    EventDefinition("scheduler.escalation.scan", "platform.scheduler", "system"),
    EventDefinition("scheduler.reconciliation.daily", "platform.scheduler", "system"),
)

SYSTEM_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("job.failed", "platform.queue", "system"),
    EventDefinition("retry.exceeded", "platform.queue", "system"),
    EventDefinition("queue.blocked", "platform.queue", "system"),
)

NOTIFICATION_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("notification.sent", "notifications.engine", "notification"),
    EventDefinition("notification.delivered", "notifications.engine", "notification"),
    EventDefinition("notification.failed", "notifications.engine", "notification"),
    EventDefinition("notification.deliver", "notifications.engine", "notification"),
    EventDefinition("workflow.approval.reminder", "workflow.engine", "domain"),
    EventDefinition("workflow.step.notification", "workflow.executor", "domain"),
    EventDefinition("invoice.approval.required", "erp.ap", "domain"),
    EventDefinition("gst.deadline.approaching", "governance.compliance", "governance"),
    EventDefinition("suspicious.activity.detected", "governance.risk", "governance"),
    EventDefinition("ai.reconciliation.suggested", "ai.runtime", "ai"),
    EventDefinition("scheduler.notifications.digest", "platform.scheduler", "system"),
)

GOVERNANCE_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("audit.log.created", "governance.audit", "governance"),
    EventDefinition("policy.violation.detected", "governance.engine", "governance"),
    EventDefinition("compliance.alert.generated", "governance.compliance", "governance"),
)

UI_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("invoice.flagged", "erp.ap", "domain"),
)

ALL_EVENTS: dict[str, EventDefinition] = {
    e.event_type: e
    for e in (
        *ERP_EVENTS,
        *WORKFLOW_EVENTS,
        *AI_EVENTS,
        *INTEGRATION_EVENTS,
        *SCHEDULER_EVENTS,
        *SYSTEM_EVENTS,
        *UI_EVENTS,
        *GOVERNANCE_EVENTS,
        *NOTIFICATION_EVENTS,
    )
}


def get_event_definition(event_type: str) -> EventDefinition | None:
    return ALL_EVENTS.get(event_type)


def validate_event_owner(event_type: str, source: str) -> bool:
    definition = get_event_definition(event_type)
    if definition is None:
        return True
    return source.startswith(definition.owner) or source == definition.owner
