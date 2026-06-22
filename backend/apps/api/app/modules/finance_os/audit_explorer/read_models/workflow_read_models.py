from __future__ import annotations

from app.modules.workflows.repositories import approval_repo, step_repo, workflow_repo


def list_approvals(org_id: str, workflow_instance_id: str) -> list[dict]:
    return approval_repo.list_for_instance(org_id, workflow_instance_id)


def list_workflow_steps(org_id: str, workflow_instance_id: str) -> list[dict]:
    return step_repo.list_steps(org_id, workflow_instance_id)


def get_workflow_instance(org_id: str, workflow_instance_id: str) -> dict | None:
    return workflow_repo.get_instance(org_id, workflow_instance_id)
