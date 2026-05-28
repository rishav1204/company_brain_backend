from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import sleep

from app.core.config import settings
from app.services.logger import log_event


@dataclass
class CircuitState:
    failure_count: int = 0
    open_until: datetime | None = None


class LlmRuntimeGuard:
    def __init__(self) -> None:
        self.circuit_by_org: dict[str, CircuitState] = {}
        self.token_budget_window_start: dict[str, datetime] = {}
        self.token_budget_used: dict[str, int] = {}

    def _circuit(self, org_id: str) -> CircuitState:
        state = self.circuit_by_org.get(org_id)
        if state is None:
            state = CircuitState()
            self.circuit_by_org[org_id] = state
        return state

    def check_circuit(self, org_id: str) -> None:
        state = self._circuit(org_id)
        if state.open_until and datetime.now(timezone.utc) < state.open_until:
            raise RuntimeError("LLM circuit is open for this org")

    def record_success(self, org_id: str) -> None:
        state = self._circuit(org_id)
        state.failure_count = 0
        state.open_until = None

    def record_failure(self, org_id: str) -> None:
        state = self._circuit(org_id)
        state.failure_count += 1
        if state.failure_count >= settings.llm_circuit_fail_threshold:
            state.open_until = datetime.now(timezone.utc) + timedelta(seconds=settings.llm_circuit_open_seconds)
            log_event("llm.circuit.opened", org_id=org_id, until=state.open_until.isoformat())

    def reserve_tokens(self, org_id: str, estimated_tokens: int) -> None:
        now = datetime.now(timezone.utc)
        start = self.token_budget_window_start.get(org_id)
        if start is None or (now - start).total_seconds() >= 60:
            self.token_budget_window_start[org_id] = now
            self.token_budget_used[org_id] = 0
        used = self.token_budget_used.get(org_id, 0)
        if used + estimated_tokens > settings.llm_tokens_per_minute_per_org:
            raise RuntimeError("LLM token budget exceeded for this org")
        self.token_budget_used[org_id] = used + estimated_tokens

    def retry_delays(self) -> list[float]:
        return [(settings.llm_retry_base_ms * (2**i)) / 1000.0 for i in range(settings.llm_max_retries)]

    def backoff(self, delay_seconds: float) -> None:
        sleep(delay_seconds)


llm_runtime_guard = LlmRuntimeGuard()
