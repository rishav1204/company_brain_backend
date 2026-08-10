"""Soft-delete capture and restore helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from app.modules.platform.control_plane.repositories.control_plane_repository import (
    control_plane_repository,
)
from app.modules.platform.control_plane.services.activity_service import activity_service


class RecycleService:
    def capture(
        self,
        *,
        org_id: str,
        entity_type: str,
        entity_id: str,
        snapshot: dict[str, Any],
        deleted_by: str | None,
        delete_reason: str | None = None,
        source: str = "user",
        retention_days: int = 30,
    ) -> dict[str, Any]:
        activity = activity_service.record(
            org_id=org_id,
            actor_user_id=deleted_by,
            actor_type="user" if source == "user" else "platform_operator",
            action="delete",
            entity_type=entity_type,
            entity_id=str(entity_id),
            summary=f"Deleted {entity_type}:{entity_id}",
            metadata={"reason": delete_reason},
        )
        return control_plane_repository.put_recycle(
            org_id=org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            snapshot=snapshot,
            deleted_by=deleted_by,
            delete_reason=delete_reason,
            source=source,
            retention_days=retention_days,
            activity_event_id=activity.get("id"),
        )

    @contextmanager
    def capture_then_delete(
        self,
        *,
        org_id: str,
        entity_type: str,
        entity_id: str,
        snapshot: dict[str, Any],
        deleted_by: str | None,
        delete_reason: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        entry = self.capture(
            org_id=org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            snapshot=snapshot,
            deleted_by=deleted_by,
            delete_reason=delete_reason,
        )
        yield entry

    def list_items(self, *, org_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        return control_plane_repository.list_recycle(org_id=org_id, limit=limit, offset=offset)

    def restore(self, recycle_id: str, *, restored_by: str | None) -> dict[str, Any]:
        row = control_plane_repository.get_recycle(recycle_id)
        if not row:
            raise LookupError("Recycle entry not found")
        if row.get("restore_status") != "available":
            raise ValueError("Entry is not available for restore")
        # Attempt registered soft-delete undo when snapshot carries full row keys.
        try:
            self._try_entity_restore(row)
        except Exception:
            # Keep mark-as-restored semantics; caller may use snapshot for manual recovery.
            pass
        updated = control_plane_repository.mark_restored(recycle_id, restored_by=restored_by)
        if not updated:
            raise ValueError("Could not restore entry")
        activity_service.record(
            org_id=row["org_id"],
            actor_user_id=restored_by,
            actor_type="platform_operator" if restored_by else "system",
            action="restore",
            entity_type=row.get("entity_type"),
            entity_id=row.get("entity_id"),
            summary=f"Restored {row.get('entity_type')}:{row.get('entity_id')}",
            before_snapshot_id=recycle_id,
            metadata={"snapshot_keys": list((row.get("snapshot") or {}).keys())[:50]},
        )
        return {**updated, "snapshot": row.get("snapshot")}

    def _try_entity_restore(self, row: dict[str, Any]) -> None:
        """Best-effort restore via entity_type_registry soft_delete_column."""
        from app.services.db import get_db_conn
        from app.services.schema_registry import table_ready

        if not table_ready("platform", "entity_type_registry"):
            return
        entity_type = row.get("entity_type")
        snapshot = row.get("snapshot") or {}
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT schema_name, table_name, soft_delete_column
                    FROM platform.entity_type_registry
                    WHERE entity_type = %s AND status = 'active'
                    """,
                    (entity_type,),
                )
                reg = cur.fetchone()
                if not reg or not reg.get("soft_delete_column"):
                    return
                schema, table, col = reg["schema_name"], reg["table_name"], reg["soft_delete_column"]
                # Only clear tombstone when id known
                cur.execute(
                    f"""
                    UPDATE {schema}.{table}
                    SET {col} = NULL
                    WHERE id::text = %s AND org_id = %s::uuid
                    """,
                    (str(row.get("entity_id")), str(row.get("org_id"))),
                )
                conn.commit()


recycle_service = RecycleService()
