from __future__ import annotations

from app.modules.platform.integrations.repositories.sync_repository import sync_repository


class SyncService:
    def create_job(self, org_id: str, *, connector_id: str, sync_type: str, metadata: dict) -> dict:
        return sync_repository.create_job(org_id, connector_id=connector_id, sync_type=sync_type, metadata=metadata or {})

    def list_jobs(self, org_id: str) -> list[dict]:
        return sync_repository.list_jobs(org_id)


sync_service = SyncService()

