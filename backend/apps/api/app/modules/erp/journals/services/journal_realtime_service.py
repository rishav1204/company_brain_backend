from __future__ import annotations

from app.modules.platform.notifications.services.realtime_service import realtime_notification_service


class JournalRealtimeService:
    def push_approved(self, org_id: str, *, journal_id: str, approved_by: str | None) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="journal.approved",
            priority="medium",
            title="Journal approved",
            body=f"Journal {journal_id} approved and ready for posting.",
            metadata={"journal_id": journal_id, "approved_by": approved_by},
        )

    def push_posted(self, org_id: str, *, journal_id: str, batch_id: str) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="journal.posted",
            priority="high",
            title="Journal posted to GL",
            body=f"Journal {journal_id} posted (batch {batch_id}).",
            metadata={"journal_id": journal_id, "batch_id": batch_id},
        )

    def push_reversed(self, org_id: str, *, journal_id: str, reversal_journal_id: str) -> None:
        realtime_notification_service.push_toast(
            org_id,
            notification_type="journal.reversed",
            priority="high",
            title="Journal reversed",
            body=f"Journal {journal_id} reversed via {reversal_journal_id}.",
            metadata={"journal_id": journal_id, "reversal_journal_id": reversal_journal_id},
        )


journal_realtime_service = JournalRealtimeService()
