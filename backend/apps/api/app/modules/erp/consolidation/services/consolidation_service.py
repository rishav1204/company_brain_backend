from __future__ import annotations

from app.modules.erp.consolidation.engine.consolidation_engine import ConsolidationResult, run_consolidation
from app.modules.erp.consolidation.repositories.consolidation_run_repository import consolidation_run_repository
from app.modules.erp.consolidation.repositories.elimination_repository import elimination_repository
from app.modules.erp.consolidation.repositories.ownership_snapshot_repository import ownership_snapshot_repository


class ConsolidationService:
    def run(
        self,
        org_id: str,
        *,
        group_company_id: str,
        fiscal_period_id: str,
        company_ids: list[str] | None = None,
        actor_user_id: str | None = None,
        dry_run: bool = False,
    ) -> ConsolidationResult:
        from app.modules.erp.consolidation.events import consolidation_events

        if not dry_run:
            consolidation_events.emit_requested(org_id, group_company_id=group_company_id)
        return run_consolidation(
            org_id,
            group_company_id=group_company_id,
            fiscal_period_id=fiscal_period_id,
            company_ids=company_ids,
            actor_user_id=actor_user_id,
            dry_run=dry_run,
        )

    def get_run(self, org_id: str, run_id: str) -> dict | None:
        run = consolidation_run_repository.get(org_id, run_id)
        if run:
            run["ownership_snapshots"] = ownership_snapshot_repository.list_for_run(org_id, run_id)
        return run

    def list_runs(self, org_id: str, *, limit: int = 50) -> list[dict]:
        return consolidation_run_repository.list_runs(org_id, limit=limit)

    def list_eliminations(self, org_id: str, run_id: str) -> list[dict]:
        return elimination_repository.list_for_run(org_id, run_id)


consolidation_service = ConsolidationService()
