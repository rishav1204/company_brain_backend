from __future__ import annotations

import json
import threading
from collections import defaultdict, deque
from typing import Any

from app.core.config import settings

_MAX_EVENTS_PER_ORG = 500
_REDIS_CHANNEL_PREFIX = "workflow:events:"


class WorkflowRealtimeHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=_MAX_EVENTS_PER_ORG))
        self._redis = None
        if settings.redis_url.strip():
            try:
                import redis

                self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            except Exception:
                self._redis = None

    def publish(self, org_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            self._events[org_id].append(event)
        if self._redis:
            try:
                self._redis.publish(f"{_REDIS_CHANNEL_PREFIX}{org_id}", json.dumps(event))
                self._redis.lpush(f"{_REDIS_CHANNEL_PREFIX}{org_id}:log", json.dumps(event))
                self._redis.ltrim(f"{_REDIS_CHANNEL_PREFIX}{org_id}:log", 0, _MAX_EVENTS_PER_ORG - 1)
            except Exception:
                pass

    def since(self, org_id: str, cursor: int = 0) -> tuple[list[dict[str, Any]], int]:
        if self._redis:
            try:
                raw = self._redis.lrange(f"{_REDIS_CHANNEL_PREFIX}{org_id}:log", 0, _MAX_EVENTS_PER_ORG - 1)
                items = [json.loads(x) for x in reversed(raw)]
                if cursor < len(items):
                    chunk = items[cursor:]
                    return chunk, cursor + len(chunk)
            except Exception:
                pass
        with self._lock:
            items = list(self._events.get(org_id, []))
        if cursor < 0:
            cursor = 0
        chunk = items[cursor:]
        return chunk, cursor + len(chunk)


workflow_realtime_hub = WorkflowRealtimeHub()
