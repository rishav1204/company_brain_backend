from __future__ import annotations

from app.modules.finance_os.agents.repositories.execution_repository import execution_repository
from app.services.repositories import agents_repo


class ExecutionService:
    def schema_ready(self) -> bool:
        return execution_repository.schema_ready()

    def create_platform_run(
        self,
        org_id: str,
        *,
        agent_type: str,
        trigger_type: str,
        status: str,
        outputs: dict,
    ) -> dict:
        return agents_repo.create_run(
            org_id=org_id,
            agent_type=agent_type,
            trigger_type=trigger_type,
            status=status,
            outputs=outputs,
        )


execution_service = ExecutionService()
