from __future__ import annotations

from app.modules.platform.events.queues.dead_letter_queue import list_dlq_depth, requeue_from_dlq


class DeadLetterEngine:
    def dlq_depth(self, queue_name: str) -> int:
        try:
            return list_dlq_depth(queue_name)
        except Exception:
            return 0

    def requeue(self, queue_name: str, *, limit: int = 10) -> int:
        try:
            return requeue_from_dlq(queue_name, limit=limit)
        except Exception:
            return 0


dead_letter_engine = DeadLetterEngine()
