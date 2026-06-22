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
    EventDefinition("erp.period.opened", "erp.fiscal", "domain"),
    EventDefinition("erp.period.soft_locked", "erp.fiscal", "domain"),
    EventDefinition("erp.period.hard_locked", "erp.fiscal", "domain"),
    EventDefinition("erp.period.closed", "erp.fiscal", "domain"),
    EventDefinition("erp.period.reopened", "erp.fiscal", "domain"),
    EventDefinition("erp.fiscal_year.closed", "erp.fiscal", "domain"),
    EventDefinition("erp.year_end.completed", "erp.fiscal", "domain"),
    EventDefinition("erp.trial_balance.generated", "erp.gl", "domain"),
    EventDefinition("erp.account.created", "erp.coa", "domain"),
    EventDefinition("erp.account.updated", "erp.coa", "domain"),
    EventDefinition("erp.gst.mapping.updated", "erp.coa", "domain"),
    EventDefinition("erp.vendor.created", "erp.ap", "domain"),
    EventDefinition("erp.gst.return.generated", "erp.tax", "domain"),
    EventDefinition("gst.transaction.recorded", "erp.tax", "domain"),
    EventDefinition("gst.mismatch.detected", "erp.tax", "domain"),
    EventDefinition("tds.calculated", "erp.tax", "domain"),
    EventDefinition("compliance.alert", "erp.tax", "domain"),
    EventDefinition("compliance.due", "erp.compliance", "domain"),
    EventDefinition("compliance.overdue", "erp.compliance", "domain"),
    EventDefinition("compliance.completed", "erp.compliance", "domain"),
    EventDefinition("compliance.escalated", "erp.compliance", "domain"),
    EventDefinition("compliance.obligation.created", "erp.compliance", "domain"),
    EventDefinition("irn.generated", "erp.tax", "domain"),
    EventDefinition("eway.bill.created", "erp.tax", "domain"),
    EventDefinition("irn.generated", "erp.tax", "domain"),
    EventDefinition("eway.bill.created", "erp.tax", "domain"),
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
    EventDefinition("bank.account.created", "erp.banking", "domain"),
    EventDefinition("bank.statement.imported", "erp.banking", "domain"),
    EventDefinition("bank.transaction.imported", "erp.banking", "domain"),
    EventDefinition("payment.executed", "erp.banking", "domain"),
    EventDefinition("payment.failed", "erp.banking", "domain"),
    EventDefinition("receipt.received", "erp.banking", "domain"),
    EventDefinition("customer.credit.limit.exceeded", "erp.ar", "domain"),
    EventDefinition("journal.posted", "erp.journals", "domain"),
    EventDefinition("erp.journal.posting.completed", "erp.journals", "domain"),
    EventDefinition("ledger.posted", "erp.gl", "domain"),
    EventDefinition("pr.created", "erp.procurement", "domain"),
    EventDefinition("pr.approved", "erp.procurement", "domain"),
    EventDefinition("po.created", "erp.procurement", "domain"),
    EventDefinition("po.approved", "erp.procurement", "domain"),
    EventDefinition("po.sent", "erp.procurement", "domain"),
    EventDefinition("grn.created", "erp.procurement", "domain"),
    EventDefinition("grn.confirmed", "erp.procurement", "domain"),
    EventDefinition("three_way_match.completed", "erp.procurement", "domain"),
    EventDefinition("three_way_match.exception", "erp.procurement", "domain"),
    EventDefinition("erp.po.created", "erp.procurement", "domain"),
    EventDefinition("erp.po.approved", "erp.procurement", "domain"),
    EventDefinition("expense.claim.created", "erp.expense", "domain"),
    EventDefinition("expense.claim.approved", "erp.expense", "domain"),
    EventDefinition("expense.claim.rejected", "erp.expense", "domain"),
    EventDefinition("expense.reimbursement.scheduled", "erp.expense", "domain"),
    EventDefinition("expense.reimbursed", "erp.expense", "domain"),
    EventDefinition("expense.receipt.extracted", "erp.expense", "domain"),
    EventDefinition("asset.created", "erp.assets", "domain"),
    EventDefinition("asset.capitalized", "erp.assets", "domain"),
    EventDefinition("asset.depreciated", "erp.assets", "domain"),
    EventDefinition("asset.transferred", "erp.assets", "domain"),
    EventDefinition("asset.disposed", "erp.assets", "domain"),
    EventDefinition("asset.impaired", "erp.assets", "domain"),
    EventDefinition("asset.candidate.detected", "erp.assets", "domain"),
    EventDefinition("inventory.received", "erp.inventory", "domain"),
    EventDefinition("inventory.issued", "erp.inventory", "domain"),
    EventDefinition("inventory.adjusted", "erp.inventory", "domain"),
    EventDefinition("inventory.transferred", "erp.inventory", "domain"),
    EventDefinition("inventory.valued", "erp.inventory", "domain"),
    EventDefinition("inventory.closed", "erp.inventory", "domain"),
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
    EventDefinition("workflow.stage.entered", "workflow.engine", "domain"),
    EventDefinition("workflow.stage.completed", "workflow.engine", "domain"),
    EventDefinition("workflow.step.system_task", "workflow.engine", "domain"),
    EventDefinition("approval.requested", "workflow.engine", "domain"),
    EventDefinition("approval.completed", "workflow.engine", "domain"),
    EventDefinition("approval.rejected", "workflow.engine", "domain"),
    EventDefinition("sla.breached", "workflow.engine", "domain"),
)

AI_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("invoice.ai.reviewed", "ai.runtime", "ai"),
    EventDefinition("invoice.extracted", "finance_os.invoice_ai", "ai"),
    EventDefinition("invoice.predicted", "finance_os.invoice_ai", "ai"),
    EventDefinition("invoice.duplicate_detected", "finance_os.invoice_ai", "ai"),
    EventDefinition("invoice.anomaly_detected", "finance_os.invoice_ai", "ai"),
    EventDefinition("invoice.pipeline.completed", "finance_os.invoice_ai", "ai"),
    EventDefinition("workflow.bottleneck.detected", "finance_os.workflow_intelligence", "ai"),
    EventDefinition("workflow.sla_risk.detected", "finance_os.workflow_intelligence", "ai"),
    EventDefinition("workflow.optimization.recommended", "finance_os.workflow_intelligence", "ai"),
    EventDefinition("workflow.health.updated", "finance_os.workflow_intelligence", "ai"),
    EventDefinition("workflow.intelligence.completed", "finance_os.workflow_intelligence", "ai"),
    EventDefinition("memory.created", "finance_os.memory", "ai"),
    EventDefinition("memory.updated", "finance_os.memory", "ai"),
    EventDefinition("memory.expired", "finance_os.memory", "ai"),
    EventDefinition("memory.high_importance.detected", "finance_os.memory", "ai"),
    EventDefinition("memory.summarized", "finance_os.memory", "ai"),
    EventDefinition("graph.updated", "finance_os.graph", "ai"),
    EventDefinition("graph.lineage.generated", "finance_os.graph", "ai"),
    EventDefinition("graph.dependency.detected", "finance_os.graph", "ai"),
    EventDefinition("graph.root_cause.generated", "finance_os.graph", "ai"),
    EventDefinition("payment.risk.detected", "ai.runtime", "ai"),
    EventDefinition("reconciliation.match.suggested", "ai.reconciliation", "ai"),
    EventDefinition("risk.detected", "ai.runtime", "ai"),
    EventDefinition("agent.run.requested", "ai.runtime", "ai"),
    EventDefinition("agent.started", "finance_os.agents", "ai"),
    EventDefinition("agent.completed", "finance_os.agents", "ai"),
    EventDefinition("agent.recommendation.created", "finance_os.agents", "ai"),
    EventDefinition("agent.workflow.created", "finance_os.agents", "ai"),
    EventDefinition("forecast.generated", "finance_os.forecasting", "ai"),
    EventDefinition("forecast.updated", "finance_os.forecasting", "ai"),
    EventDefinition("forecast.risk.detected", "finance_os.forecasting", "ai"),
    EventDefinition("forecast.accuracy.calculated", "finance_os.forecasting", "ai"),
    EventDefinition("report.generated", "erp.reporting", "domain"),
    EventDefinition("report.exported", "erp.reporting", "domain"),
    EventDefinition("report.snapshot.created", "erp.reporting", "domain"),
    EventDefinition("reports.generate.requested", "erp.reporting", "domain"),
    EventDefinition("reports.generate.completed", "erp.reporting", "domain"),
    EventDefinition("reports.refresh.requested", "erp.reporting", "domain"),
    EventDefinition("kpi.updated", "finance_os.analytics", "ai"),
    EventDefinition("insight.generated", "finance_os.analytics", "ai"),
    EventDefinition("risk.detected", "finance_os.analytics", "ai"),
    EventDefinition("dashboard.refreshed", "finance_os.analytics", "ai"),
    EventDefinition("analytics.refresh.requested", "finance_os.analytics", "ai"),
    EventDefinition("ai.ocr.requested", "ai.runtime", "ai"),
)

INTEGRATION_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("payment.executed", "erp.treasury", "domain"),
    EventDefinition("bank.transaction.imported", "erp.treasury", "domain"),
    EventDefinition("reconciliation.suggested", "erp.reconciliation", "domain"),
    EventDefinition("reconciliation.completed", "erp.reconciliation", "domain"),
    EventDefinition("reconciliation.exception.created", "erp.reconciliation", "domain"),
    EventDefinition("reconciliation.adjustment.required", "erp.reconciliation", "domain"),
    EventDefinition("reconciliation.adjustment.posted", "erp.reconciliation", "domain"),
    EventDefinition("consolidation.completed", "erp.consolidation", "domain"),
    EventDefinition("consolidation.failed", "erp.consolidation", "domain"),
    EventDefinition("consolidation.requested", "erp.consolidation", "domain"),
    EventDefinition("elimination.generated", "erp.consolidation", "domain"),
    EventDefinition("intercompany.created", "erp.consolidation", "domain"),
    EventDefinition("intercompany.mismatch.detected", "erp.consolidation", "domain"),
    EventDefinition("entity.closed", "erp.consolidation", "domain"),
    EventDefinition("cash.position.updated", "erp.treasury", "domain"),
    EventDefinition("liquidity_alert.created", "erp.treasury", "domain"),
    EventDefinition("cash.forecast.updated", "erp.treasury", "domain"),
    EventDefinition("treasury.risk.detected", "erp.treasury", "domain"),
    EventDefinition("bank.feed.imported", "integration.bank", "integration"),
    EventDefinition("bank.statement.imported", "integration.bank", "integration"),
    EventDefinition("gst.response.received", "integration.gst", "integration"),
    EventDefinition("webhook.received", "integration.webhooks", "integration"),
    EventDefinition("webhook.delivered", "api_gateway", "integration"),
    EventDefinition("webhook.failed", "api_gateway", "integration"),
    EventDefinition("api.key.created", "api_gateway", "integration"),
    EventDefinition("api.key.revoked", "api_gateway", "integration"),
    EventDefinition("integration.connected", "api_gateway", "integration"),
)

SCHEDULER_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("scheduler.tick", "platform.scheduler", "system"),
    EventDefinition("scheduler.sla.scan", "platform.scheduler", "system"),
    EventDefinition("scheduler.escalation.scan", "platform.scheduler", "system"),
    EventDefinition("scheduler.reconciliation.daily", "platform.scheduler", "system"),
    EventDefinition("scheduler.compliance.daily", "platform.scheduler", "system"),
    EventDefinition("scheduler.treasury.daily", "platform.scheduler", "system"),
    EventDefinition("scheduler.reports.daily", "platform.scheduler", "system"),
    EventDefinition("scheduler.analytics.daily", "platform.scheduler", "system"),
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
    EventDefinition("audit.timeline.updated", "finance_os.audit_explorer", "governance"),
    EventDefinition("audit.evidence.linked", "finance_os.audit_explorer", "governance"),
    EventDefinition("audit.ai_decision.recorded", "finance_os.audit_explorer", "governance"),
    EventDefinition("policy.approved", "governance.policy_engine", "governance"),
    EventDefinition("policy.denied", "governance.policy_engine", "governance"),
    EventDefinition("policy.override.required", "governance.policy_engine", "governance"),
    EventDefinition("policy.risk.detected", "governance.policy_engine", "governance"),
    EventDefinition("policy.evaluated", "governance.policy_engine", "governance"),
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
