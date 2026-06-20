from __future__ import annotations

from datetime import datetime, timezone

from app.modules.finance_os.memory.repositories.entry_repository import entry_repository
from app.modules.finance_os.memory.repositories.reference_repository import reference_repository
from app.services.repositories import memory_repo


class FinanceOsMemoryService:
    def get(self, org_id: str, memory_id: str) -> dict | None:
        entry = entry_repository.get(org_id, memory_id)
        if not entry:
            return None
        refs = reference_repository.list_for_memory(org_id, memory_id)
        return {**entry, "references": refs}

    def list_entity(self, org_id: str, *, entity_type: str, entity_id: str, memory_type: str | None = None) -> list[dict]:
        return entry_repository.list_active(
            org_id, entity_type=entity_type, entity_id=entity_id, memory_type=memory_type, limit=200
        )

    def summary(self, org_id: str) -> dict:
        by_type = entry_repository.summary_by_type(org_id)
        return {"categories": by_type, "generated_at": datetime.now(timezone.utc).isoformat()}

    def sync_legacy_status(self, org_id: str, memory_record_id: str | None, status: str) -> None:
        if memory_record_id:
            memory_repo.update_memory_status(org_id=org_id, memory_id=memory_record_id, status=status)


finance_os_memory_service = FinanceOsMemoryService()
