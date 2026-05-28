from app.modules.workflows.repositories.approval_repository import ApprovalRepository
from app.modules.workflows.repositories.escalation_repository import EscalationRepository
from app.modules.workflows.repositories.workflow_repository import WorkflowRepository
from app.modules.workflows.repositories.workflow_step_repository import WorkflowStepRepository
from app.modules.workflows.repositories.workflow_task_repository import WorkflowTaskRepository

workflow_repo = WorkflowRepository()
step_repo = WorkflowStepRepository()
approval_repo = ApprovalRepository()
task_repo = WorkflowTaskRepository()
escalation_repo = EscalationRepository()

__all__ = [
    "workflow_repo",
    "step_repo",
    "approval_repo",
    "task_repo",
    "escalation_repo",
]
