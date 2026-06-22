from __future__ import annotations

from app.modules.erp.consolidation.repositories.elimination_repository import elimination_repository


class EliminationService:
    def list_for_run(self, org_id: str, consolidation_run_id: str) -> list[dict]:
        return elimination_repository.list_for_run(org_id, consolidation_run_id)


elimination_service = EliminationService()
