from collections import deque
from dataclasses import dataclass


@dataclass
class QueueMessage:
    idempotency_key: str
    payload: dict
    attempts: int = 0


class InMemoryQueue:
    def __init__(self) -> None:
        self.main: deque[QueueMessage] = deque()
        self.dlq: deque[QueueMessage] = deque()
        self.processed_keys: set[str] = set()

    def enqueue(self, message: QueueMessage) -> None:
        self.main.append(message)

    def process_next(self, max_attempts: int = 3) -> dict:
        if not self.main:
            return {"status": "empty"}

        message = self.main.popleft()
        if message.idempotency_key in self.processed_keys:
            return {"status": "deduped", "idempotency_key": message.idempotency_key}

        message.attempts += 1
        should_fail = bool(message.payload.get("force_fail"))
        if should_fail and message.attempts < max_attempts:
            self.main.append(message)
            return {"status": "retry", "attempts": message.attempts}

        if should_fail:
            self.dlq.append(message)
            return {"status": "dlq", "attempts": message.attempts}

        self.processed_keys.add(message.idempotency_key)
        return {"status": "processed", "idempotency_key": message.idempotency_key}


queue_service = InMemoryQueue()
