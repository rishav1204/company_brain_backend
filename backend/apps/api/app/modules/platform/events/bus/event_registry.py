from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventDefinition:
    event_type: str
    owner: str
    category: str
    version: str = "v1"
    financial: bool = False
    deprecated: bool = False
    description: str = ""


ERP_EVENTS: tuple[EventDefinition, ...] = (
    EventDefinition("erp.invoice.created", "erp.ap", "domain", financial=True),
    EventDefinition("erp.invoice.approved", "erp.ap", "domain", financial=True),
    EventDefinition("erp.invoice.updated", "erp.ap", "domain", financial=True),
    EventDefinition("erp.payment.completed", "erp.treasury", "domain", financial=True),
    EventDefinition("erp.payment.failed", "erp.treasury", "domain", financial=True),
    EventDefinition("erp.journal.created", "erp.journals", "domain", financial=True),
    EventDefinition("erp.journal.approved", "erp.journals", "domain", financial=True),
    EventDefinition("erp.journal.posted", "erp.journals", "domain", financial=True),
    EventDefinition("erp.journal.reversed", "erp.journals", "domain", financial=True),
    EventDefinition("journal.created", "erp.journals", "domain", financial=True),
    EventDefinition("journal.approved", "erp.journals", "domain", financial=True),
    EventDefinition("journal.reversed", "erp.journals", "domain", financial=True),
    EventDefinition("erp.ledger.posted", "erp.gl", "domain", financial=True),
    EventDefinition("erp.ledger.reversed", "erp.gl", "domain", financial=True),
    EventDefinition("erp.fiscal_period.locked", "erp.gl", "domain", financial=True),
    EventDefinition("erp.fiscal_period.closed", "erp.gl", "domain", financial=True),
    EventDefinition("erp.period.opened", "erp.fiscal", "domain", financial=True),
    EventDefinition("erp.period.soft_locked", "erp.fiscal", "domain", financial=True),
    EventDefinition("erp.period.hard_locked", "erp.fiscal", "domain", financial=True),
    EventDefinition("erp.period.closed", "erp.fiscal", "domain", financial=True),
    EventDefinition("erp.period.reopened", "erp.fiscal", "domain", financial=True),
    EventDefinition("erp.fiscal_year.closed", "erp.fiscal", "domain", financial=True),
    EventDefinition("erp.year_end.completed", "erp.fiscal", "domain", financial=True),
    EventDefinition("erp.trial_balance.generated", "erp.gl", "domain", financial=True),
    EventDefinition("erp.account.created", "erp.coa", "domain"),
    EventDefinition("erp.account.updated", "erp.coa", "domain"),
    EventDefinition("erp.gst.mapping.updated", "erp.coa", "domain"),
    EventDefinition("erp.vendor.created", "erp.ap", "domain"),
    EventDefinition("erp.gst.return.generated", "erp.tax", "domain", financial=True),
    EventDefinition("gst.transaction.recorded", "erp.tax", "domain", financial=True),
    EventDefinition("gst.mismatch.detected", "erp.tax", "domain", financial=True),
    EventDefinition("tds.calculated", "erp.tax", "domain", financial=True),
    EventDefinition("compliance.alert", "erp.tax", "domain"),
    EventDefinition("compliance.due", "erp.compliance", "domain"),
    EventDefinition("compliance.overdue", "erp.compliance", "domain"),
    EventDefinition("compliance.completed", "erp.compliance", "domain"),
    EventDefinition("compliance.escalated", "erp.compliance", "domain"),
    EventDefinition("compliance.obligation.created", "erp.compliance", "domain"),
    EventDefinition("irn.generated", "erp.tax", "domain", financial=True),
    EventDefinition("eway.bill.created", "erp.tax", "domain"),
    EventDefinition("erp.reconciliation.pending", "erp.reconciliation", "domain", financial=True),
    EventDefinition("invoice.created", "erp.ap", "domain", financial=True),
    EventDefinition("invoice.due", "erp.ap", "domain", financial=True),
    EventDefinition("invoice.received", "erp.ap", "domain", financial=True),
    EventDefinition("payment.scheduled", "erp.ap", "domain", financial=True),
    EventDefinition("payment.completed", "erp.treasury", "domain", financial=True),
    EventDefinition("sales.invoice.created", "erp.ar", "domain", financial=True),
    EventDefinition("invoice.issued", "erp.ar", "domain", financial=True),
    EventDefinition("invoice.overdue", "erp.ar", "domain", financial=True),
    EventDefinition("collection.required", "erp.ar", "domain", financial=True),
    EventDefinition("payment.received", "erp.ar", "domain", financial=True),
    EventDefinition("customer.payment.received", "erp.ar", "domain", financial=True),
    EventDefinition("bank.account.created", "erp.banking", "domain"),
    EventDefinition("bank.statement.imported", "erp.banking", "domain", financial=True),
    EventDefinition("bank.transaction.imported", "erp.banking", "domain", financial=True),
    EventDefinition("payment.executed", "erp.banking", "domain", financial=True),
    EventDefinition("payment.failed", "erp.banking", "domain", financial=True),
    EventDefinition("receipt.received", "erp.banking", "domain", financial=True),
    EventDefinition("customer.credit.limit.exceeded", "erp.ar", "domain", financial=True),
    EventDefinition("journal.posted", "erp.journals", "domain", financial=True),
    EventDefinition("erp.journal.posting.completed", "erp.journals", "domain", financial=True),
    EventDefinition("ledger.posted", "erp.gl", "domain", financial=True),
    EventDefinition("pr.created", "erp.procurement", "domain", financial=True),
    EventDefinition("pr.approved", "erp.procurement", "domain", financial=True),
    EventDefinition("po.created", "erp.procurement", "domain", financial=True),
    EventDefinition("po.approved", "erp.procurement", "domain", financial=True),
    EventDefinition("po.sent", "erp.procurement", "domain", financial=True),
    EventDefinition("grn.created", "erp.procurement", "domain", financial=True),
    EventDefinition("grn.confirmed", "erp.procurement", "domain", financial=True),
    EventDefinition("three_way_match.completed", "erp.procurement", "domain", financial=True),
    EventDefinition("three_way_match.exception", "erp.procurement", "domain", financial=True),
    EventDefinition("erp.po.created", "erp.procurement", "domain", financial=True),
    EventDefinition("erp.po.approved", "erp.procurement", "domain", financial=True),
    EventDefinition("expense.claim.created", "erp.expense", "domain", financial=True),
    EventDefinition("expense.claim.approved", "erp.expense", "domain", financial=True),
    EventDefinition("expense.claim.rejected", "erp.expense", "domain", financial=True),
    EventDefinition("expense.reimbursement.scheduled", "erp.expense", "domain", financial=True),
    EventDefinition("expense.reimbursed", "erp.expense", "domain", financial=True),
    EventDefinition("expense.receipt.extracted", "erp.expense", "domain"),
    EventDefinition("asset.created", "erp.assets", "domain", financial=True),
    EventDefinition("asset.capitalized", "erp.assets", "domain", financial=True),
    EventDefinition("asset.depreciated", "erp.assets", "domain", financial=True),
    EventDefinition("asset.transferred", "erp.assets", "domain", financial=True),
    EventDefinition("asset.disposed", "erp.assets", "domain", financial=True),
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
    EventDefinition("erp.command.requested", "finance_os.erp_command_bridge", "domain"),
    EventDefinition("erp.command.approved", "finance_os.erp_command_bridge", "domain"),
    EventDefinition("erp.command.rejected", "finance_os.erp_command_bridge", "domain"),
    EventDefinition("erp.command.executed", "finance_os.erp_command_bridge", "domain"),
    EventDefinition("erp.command.failed", "finance_os.erp_command_bridge", "domain"),
    EventDefinition("erp.command.approval_pending", "finance_os.erp_command_bridge", "domain"),
    EventDefinition("erp.command.duplicate", "finance_os.erp_command_bridge", "domain"),
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
