from __future__ import annotations

from app.modules.workflows.repositories import task_repo, workflow_repo


class DocumentReviewWorkflowService:
    def open_review_task(
        self,
        org_id: str,
        *,
        document_id: str,
        assigned_to: str | None,
        reason: str,
        payload: dict | None = None,
        trace_id: str | None = None,
    ) -> dict:
        # Create a workflow instance without executing a full workflow definition (safe for now).
        instance = workflow_repo.create_instance(
            org_id=org_id,
            workflow_type="DOCUMENT_REVIEW",
            started_by=assigned_to,
            definition_id=None,
            entity_type="document",
            entity_id=document_id,
            metadata={"reason": reason, "trace_id": trace_id or "", **(payload or {})},
            status="waiting_approval",
        )
        task = task_repo.create_task(
            org_id=org_id,
            workflow_instance_id=instance["id"],
            task_type="document_review",
            assigned_to=assigned_to,
            payload={"document_id": document_id, "reason": reason, **(payload or {})},
        )
        return {"workflow_instance": instance, "task": task}


document_review_workflow_service = DocumentReviewWorkflowService()

