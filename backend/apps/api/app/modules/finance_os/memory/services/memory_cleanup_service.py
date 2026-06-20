from __future__ import annotations

from datetime import datetime, timezone

from app.modules.finance_os.memory.events.memory_events import emit_memory_expired
from app.modules.finance_os.memory.repositories.entry_repository import entry_repository
from app.modules.finance_os.memory.services.memory_service import finance_os_memory_service
from app.services.repositories import memory_repo


def _is_expired(row: dict) -> bool:
    expires = row.get("expires_at")
    if not expires:
        return False
    try:
        ts = expires if isinstance(expires, datetime) else datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
        return ts <= datetime.now(timezone.utc)
    except Exception:
        return False


def apply_cleanup(org_id: str, *, trace_id: str | None = None) -> dict:
    expired = archived = 0
    for row in entry_repository.list_for_decay(org_id):
        policy = row.get("ttl_policy", "90d")
        if policy == "forever":
            continue
        if not _is_expired(row):
            continue
        memory_id = row["id"]
        if policy == "180d":
            entry_repository.update_status(org_id, memory_id, "archived")
            archived += 1
            status = "archived"
        else:
            entry_repository.update_status(org_id, memory_id, "expired")
            expired += 1
            status = "expired"
            emit_memory_expired(org_id, {"memory_id": memory_id}, trace_id=trace_id)
        finance_os_memory_service.sync_legacy_status(org_id, row.get("memory_record_id"), status)
    platform_expired = 0
    try:
        from app.services.memory_service import apply_memory_decay

        platform = apply_memory_decay(org_id=org_id)
        platform_expired = int(platform.get("expired", 0))
    except Exception:
        pass
    return {"expired": expired, "archived": archived, "platform_expired": platform_expired}
