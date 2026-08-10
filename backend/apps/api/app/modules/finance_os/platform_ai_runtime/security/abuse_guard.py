"""AI cost & abuse protection for M38 runtime (Phase 8 Wave 3 / AI-18 surface)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from app.core.config import settings
from app.services.logger import log_event


class AIBudgetExceeded(PermissionError):
    """Raised when AI runtime budget / rate limits are exceeded."""


class AIAbuseGuard:
    """In-process sliding-window limits with Redis optional enhancement later.

    Reuses billing metering for quota; this layer prevents recursive/explosive local abuse
    (prompt spam, huge plans, tool floods).
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._chat_events: dict[str, deque[float]] = defaultdict(deque)
        self._run_tool_counts: dict[str, int] = {}

    def check_chat_rate(self, *, org_id: str, user_id: str) -> None:
        limit = max(1, int(settings.m38_chat_rate_limit_per_minute or 30))
        key = f"{org_id}:{user_id}"
        now = time.time()
        with self._lock:
            q = self._chat_events[key]
            while q and now - q[0] > 60.0:
                q.popleft()
            if len(q) >= limit:
                log_event(
                    "m38.security.budget_violation",
                    kind="chat_rate",
                    org_id=org_id,
                    user_id=user_id,
                    limit=limit,
                )
                raise AIBudgetExceeded(f"Chat rate limit exceeded ({limit}/min)")
            q.append(now)

    def start_run(self, *, run_id: str) -> None:
        with self._lock:
            self._run_tool_counts[run_id] = 0

    def check_tool_step(self, *, run_id: str, org_id: str = "") -> None:
        limit = max(1, int(settings.m38_max_tools_per_run or 40))
        with self._lock:
            count = self._run_tool_counts.get(run_id, 0) + 1
            self._run_tool_counts[run_id] = count
            if count > limit:
                log_event(
                    "m38.security.budget_violation",
                    kind="max_tools",
                    org_id=org_id,
                    run_id=run_id,
                    limit=limit,
                    count=count,
                )
                raise AIBudgetExceeded(f"Max tools per run exceeded ({limit})")

    def finish_run(self, *, run_id: str) -> None:
        with self._lock:
            self._run_tool_counts.pop(run_id, None)

    def check_context_size(self, *, text: str, org_id: str = "") -> None:
        limit = max(1000, int(settings.m38_max_context_chars or 24000))
        if len(text or "") > limit:
            log_event(
                "m38.security.budget_violation",
                kind="context_explosion",
                org_id=org_id,
                size=len(text or ""),
                limit=limit,
            )
            raise AIBudgetExceeded(f"Context size exceeds budget ({limit} chars)")

    def check_plan_size(self, *, node_count: int, org_id: str = "") -> None:
        limit = max(1, int(settings.m38_max_plan_nodes or 25))
        if node_count > limit:
            log_event(
                "m38.security.budget_violation",
                kind="plan_nodes",
                org_id=org_id,
                count=node_count,
                limit=limit,
            )
            raise AIBudgetExceeded(f"Plan exceeds max nodes ({limit})")


ai_abuse_guard = AIAbuseGuard()
