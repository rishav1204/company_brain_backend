from datetime import datetime, timedelta, timezone

from app.services.repositories import memory_repo


def retention_action(memory_type: str, created_at: datetime) -> str:
    age = datetime.now(timezone.utc) - created_at
    if memory_type == "short_term" and age > timedelta(days=7):
        return "expire"
    if memory_type in {"long_term", "workflow"} and age > timedelta(days=730):
        return "archive"
    if memory_type == "decision":
        return "retain"
    return "retain"


def apply_memory_decay(org_id: str) -> dict:
    expired = 0
    archived = 0
    retained = 0
    for row in memory_repo.list_all_for_decay(org_id=org_id):
        action = retention_action(row["memory_type"], row["created_at"])
        if action == "expire":
            memory_repo.update_memory_status(org_id=org_id, memory_id=row["id"], status="expired")
            expired += 1
        elif action == "archive":
            memory_repo.update_memory_status(org_id=org_id, memory_id=row["id"], status="archived")
            archived += 1
        else:
            memory_repo.update_memory_status(org_id=org_id, memory_id=row["id"], status="retained")
            retained += 1
    return {"expired": expired, "archived": archived, "retained": retained}
