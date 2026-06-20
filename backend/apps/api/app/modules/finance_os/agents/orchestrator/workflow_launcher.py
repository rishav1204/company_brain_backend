from __future__ import annotations

WORKFLOW_MAP = {
    "workflow_launch": "AP_INVOICE_APPROVAL",
    "exception_raise": "RECONCILIATION_REVIEW",
    "collection_action": "COLLECTION_FOLLOWUP",
    "ledger_suggestion": "AP_INVOICE_APPROVAL",
}


class WorkflowLauncher:
    def launch(
        self,
        org_id: str,
        *,
        workflow_key: str,
        user_id: str,
        entity_type: str = "workflow",
        entity_id: str | None = None,
        metadata: dict | None = None,
        trace_id: str | None = None,
    ) -> dict | None:
        from app.modules.workflows.services.workflow_service import workflow_service

        if not workflow_service.schema_ready():
            return None
        return workflow_service.start_workflow(
            org_id=org_id,
            user_id=user_id or "agent-runtime",
            workflow_key=workflow_key,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
            trace_id=trace_id,
        )


workflow_launcher = WorkflowLauncher()
