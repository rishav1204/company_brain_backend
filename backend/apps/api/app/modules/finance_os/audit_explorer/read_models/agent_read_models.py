from __future__ import annotations

from app.modules.finance_os.agents.repositories.execution_repository import execution_repository
from app.modules.finance_os.agents.repositories.recommendation_repository import recommendation_repository


def get_execution(org_id: str, execution_id: str) -> dict | None:
    return execution_repository.get(org_id, execution_id)


def list_recommendations(org_id: str, execution_id: str) -> list[dict]:
    return recommendation_repository.list_for_execution(org_id, execution_id)
